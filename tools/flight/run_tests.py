"""Tests and mutation twins for the co-op flight record tools. One command from the repo root:

    python -I tools/flight/run_tests.py          # everything; prints ALL OK

  (default)      Python tests, the C++ build and tests (with their mutation twins), the C++ write / Python read
                 cross tests, and the Python mutation twin
  --quick        only the fast Python tests (a few seconds); prints QUICK OK, never ALL OK
  --no-cpp       skip the C++ phase (the cross tests are skipped too); prints PYTHON OK, never ALL OK
  --no-twin      skip the Python mutation twin; prints TESTS OK, never ALL OK

The twin copies the Python sources to a temp folder, breaks one thing at a time and requires the suite to fail.
Environment: COFR_SRC=<dir> tests the Python sources in that folder (the twin uses it), COFR_BUILD_DIR=<dir> is the C++
build folder (default: a folder in the system temp dir, so nothing is written into the repo), COFR_CROSS_DIR=<dir> holds
files written by the C++ tests (set by this script).
"""
import contextlib
import io
import json
import glob
import os
import shutil
import struct
import subprocess
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.environ.get("COFR_SRC") or HERE
sys.path.insert(0, SRC)
import cofr as C  # noqa: E402
import schema as S  # noqa: E402
import analyze as A  # noqa: E402
import shrink as SH  # noqa: E402
import gentest as G  # noqa: E402
import report as R  # noqa: E402
import regress as RG  # noqa: E402

QUICK = "--quick" in sys.argv
slow = unittest.skipIf(QUICK, "slow: skipped by --quick")
GOLDEN = os.path.join(HERE, "golden")
SCHEMAS = os.path.join(HERE, "schemas")
CPP_DIR = os.path.join(HERE, "cpp")
CROSS = os.environ.get("COFR_CROSS_DIR")
TOY = os.path.join(SRC, "toy_replay.py")
REPLAY = [sys.executable, "-I", TOY, "{fixture}"]


# ---------------------------------------------------------------- synthetic traces

class TB:
    """Builds the trace of one machine from records given in milliseconds."""

    def __init__(self, slot, wall_skew_ms=0, instance=None, reason=1, schema=None, meta=None):
        self.h = {"slot": slot, "role": 0 if slot == 0 else 1, "reason": reason, "session": 9, "epoch": 1, "proto_version": 3,
                  "wall_unix_ms": 1_000_000 + wall_skew_ms, "records_dropped": 0}
        self.schema = schema
        self.recs = []
        m = {"label": instance or ("inst%d" % slot)}
        m.update(meta or {})
        self.add(C.T_META, 0, meta=m)
        if schema is not None:
            self.add(C.T_SCHEMA, 0, schema=schema)

    def add(self, ty, t_ms, **f):
        r = {"type": ty, "mono_us": int(t_ms * 1000), "frame": int(t_ms / 16)}
        r.update(f)
        self.recs.append(r)

    def net(self, out, t_ms, peer, mtype, seq, raw, epoch=1, flags=0):
        self.add(C.T_NET_OUT if out else C.T_NET_IN, t_ms, peer=peer, channel=0 if out else 0xFF, mux=0xC0, msg_type=mtype, decode=0,
                 session=9, epoch=epoch, seq=seq, seq_hi=seq, raw=raw, truncated=bool(flags))

    def txn(self, ty, t_ms, seq, h, flags=0, origin=0):
        """flags are the applied flags of a TxnApplied record (1 snapshot, 2 repair, 4 baseline, 8 catch-up in the default schema)."""
        if ty == C.T_TXN_CAPTURED:
            self.add(ty, t_ms, kind=0, intent_id=0, seq=seq, effect_count=1, hash=h, cause=0, epoch=1)
        else:
            self.add(ty, t_ms, seq=seq, epoch=1, origin=origin, index=0, applied_flags=flags, cause=0, effect_tag=0, hash=h)

    def digest(self, t_ms, cat, seq, hash_, keys=None, shards=None, bucketed=False):
        self.add(C.T_DIGEST, t_ms, category=cat, epoch=1, seq=seq, hash=hash_, item_count=0, shards=shards or [], keys=keys or {}, bucketed=bucketed)

    def own(self, t_ms, op, actor, epoch, frm, to):
        self.add(C.T_OWNERSHIP, t_ms, op=op, actor=actor, epoch=epoch, from_slot=frm, to_slot=to, reason=0, txn_id=0)

    def data(self):
        return C.dumps(self.h, sorted(self.recs, key=lambda r: r["mono_us"]), self.schema)

    def trace(self):
        return C.loads(self.data(), "slot%d" % self.h["slot"])


def good_hash(seq):
    return 0x1000 + seq


def scenario(bad_seq=None, lost=(), digest2="differ", dup_seq=None, clean_extras=False, instance1=None, late_tail=0):
    """3 machines, host slot 0, clients 1 and 2; slot 2's wall clock is 500 ms fast. 5 ms latency each way."""
    tb = [TB(0), TB(1, instance=instance1), TB(2, wall_skew_ms=500)]
    for seq, t in ((1, 100), (2, 200), (3, 300), (4, 400)):
        tb[0].txn(C.T_TXN_CAPTURED, t - 1, seq, good_hash(seq))
        tb[0].txn(C.T_TXN_APPLIED, t, seq, good_hash(seq))
        for c in (1, 2):
            raw = bytes([4, seq, c, 0xAB])
            tb[0].net(True, t, c, 4, seq, raw)
            if (seq, c) in lost:
                continue
            tb[c].net(False, t + 5, 0, 4, seq, raw)
            h = 0xBAD if (bad_seq == seq and c == 1) else good_hash(seq)
            tb[c].txn(C.T_TXN_APPLIED, t + 6, seq, h)
            ack = bytes([5, seq, c])
            tb[c].net(True, t + 7, 0, 5, seq, ack)
            tb[0].net(False, t + 12, c, 5, seq, ack)
            if dup_seq == seq and c == 1:
                tb[c].net(False, t + 9, 0, 4, seq, raw)
    for seq, c in lost:  # retransmit 30 ms later
        raw = bytes([4, seq, c, 0xAB])
        t = seq * 100 + 30
        tb[0].net(True, t, c, 4, seq, raw)
        tb[c].net(False, t + 5, 0, 4, seq, raw)
        tb[c].txn(C.T_TXN_APPLIED, t + 6, seq, good_hash(seq))
        tb[c].net(True, t + 7, 0, 5, seq, bytes([5, seq, c]))
        tb[0].net(False, t + 12, c, 5, seq, bytes([5, seq, c]))
    for t in (250,):
        for s in range(3):
            tb[s].digest(t, 0, 1, 0xAAAA, keys={0x10: 5, 0x20: 6})
    if digest2 == "differ":
        tb[0].digest(700, 0, 2, 0x1111, keys={0x10: 5, 0x20: 6})
        tb[1].digest(700, 0, 2, 0x2222, keys={0x10: 5, 0x20: 7})
        tb[2].digest(700, 0, 2, 0x1111, keys={0x10: 5, 0x20: 6})
    elif digest2 == "same":
        for s in range(3):
            tb[s].digest(700, 0, 2, 0x1111, keys={0x10: 5, 0x20: 6})
    if clean_extras:
        tb[1].txn(C.T_TXN_APPLIED, 215, 2, 0, flags=2)   # a repair restating state, with a different hash: not a divergence
        for s in range(3):
            tb[s].own(500, 0, 5, 3, 255, 1)
            tb[s].own(510, 0, 5, 3, 255, 1)                          # idempotent regrant, same epoch
    if late_tail:
        for s in range(3):
            tb[s].add(C.T_MARKER, late_tail, kind=0, text="tick")
    return [t.trace() for t in tb]


def read_golden(name):
    return C.load(os.path.join(GOLDEN, name))


def read_bytes(path):
    with open(path, "rb") as f:
        return f.read()


# ---------------------------------------------------------------- tests

class FormatTests(unittest.TestCase):
    def test_roundtrip_all_types(self):
        sch = S.Schema({"game": "t", "custom_records": {"40": {"name": "Spawn", "fields": [{"name": "id", "type": "u32"}, {"name": "label", "type": "str16"}]}}})
        recs = [
            {"type": 1, "mono_us": 0, "frame": 0, "meta": {"label": "A B", "build": "7"}},
            {"type": 9, "mono_us": 0, "frame": 0, "schema": sch},
            {"type": 3, "mono_us": 5, "frame": 1, "peer": 2, "channel": 0xFF, "mux": 0xC0, "msg_type": 4, "decode": 0, "session": 300,
             "epoch": 70000, "seq": 1 << 40, "seq_hi": (1 << 40) + 2, "raw_len": 99, "raw": b"\x00\x01\xfe", "truncated": True},
            {"type": 4, "mono_us": 9, "frame": 2, "kind": 1, "intent_id": 129, "seq": 300, "effect_count": 3, "hash": 1 << 63, "cause": 2, "epoch": 4},
            {"type": 5, "mono_us": 10, "frame": 2, "seq": 300, "epoch": 4, "origin": 1, "index": 2, "applied_flags": 9, "cause": 3, "effect_tag": 40,
             "hash": (1 << 64) - 1},
            {"type": 6, "mono_us": 11, "frame": 3, "op": 3, "actor": 0xFF00000000001001, "epoch": 2, "from_slot": 1, "to_slot": 255, "reason": 9, "txn_id": 77},
            {"type": 7, "mono_us": 12, "frame": 3, "category": 2, "epoch": 3, "seq": 8, "hash": 0xFEEDFACE, "item_count": 5,
             "shards": [1, 2, 3], "keys": {1 << 63: 5}, "derived": True, "bucketed": True},
            {"type": 8, "mono_us": 13, "frame": 3, "kind": 4, "text": "desync é"},
            {"type": 40, "mono_us": 14, "frame": 3, "fields": {"id": 7, "label": "orc"}},
            {"type": 99, "mono_us": 14, "frame": 4, "payload": b"\x09\x09"},
        ]
        h = {"slot": 3, "role": 1, "reason": 2, "proto_version": 5, "wall_unix_ms": 1234567890123, "dump_t_us": 99, "records_dropped": 8,
             "session": 4, "epoch": 6}
        tr = C.loads(C.dumps(h, recs, sch))
        self.assertFalse(tr["truncated"])
        self.assertEqual(tr["header"]["reason_name"], "crash")
        self.assertEqual(tr["header"]["role_name"], "client")
        self.assertEqual((tr["header"]["session"], tr["header"]["epoch"], tr["header"]["record_count"]), (4, 6, 10))
        self.assertEqual(tr["header"]["records_dropped"], 8)
        self.assertEqual(tr["header"]["proto_version"], 5)
        self.assertEqual(tr["header"]["instance"], "A B")
        got = tr["records"]
        self.assertEqual(len(got), 10)
        for want, g in zip(recs, got):
            for k, v in want.items():
                if k == "schema":
                    continue
                self.assertEqual(g[k], v, (want["type"], k))
        self.assertEqual(got[5]["ref"], "actor:FF00000000001001")
        self.assertEqual(got[9]["name"], "Unknown99")
        self.assertEqual(got[8]["name"], "Spawn")
        self.assertEqual(got[2]["flags"], 1)
        self.assertEqual(got[6]["flags"], 2 | 8)
        self.assertEqual(tr["schema"].game, "t")
        self.assertIn("seq=300", C.describe(got[3]))
        self.assertIn("peer 2", C.describe(got[2]))
        self.assertIn("[test-step]", C.describe(got[7]))
        self.assertIn("rejectedStale", C.describe(got[5]))
        self.assertIn("label=orc", C.describe(got[8], tr["schema"]))

    def test_datagram_hash_differs_for_different_datagrams(self):
        recs = [{"type": 2, "mono_us": i, "frame": 0, "peer": 1, "raw": bytes([i, 7, 7, 7])} for i in range(3)]
        got = C.loads(C.dumps({"slot": 0}, recs))["records"]
        self.assertEqual(len({r["dhash"] for r in got}), 3)

    def test_hash_helpers_match_known_values(self):
        # FNV-1a 64 of "a" and of the empty string are published constants
        self.assertEqual(C.hash64(b""), 0xCBF29CE484222325)
        self.assertEqual(C.hash64(b"a"), 0xAF63DC4C8601EC8C)
        self.assertEqual(C.bucket_mix(1, 2), C.bucket_mix(1, 2))
        self.assertNotEqual(C.bucket_mix(1, 2), C.bucket_mix(1, 3))
        self.assertNotEqual(C.bucket_mix(1, 2), C.bucket_mix(2, 2))
        a, ha = C.bucketed_digest([(5, 1), (6, 2)])
        b, hb = C.bucketed_digest([(6, 2), (5, 1)])
        self.assertEqual((a, ha), (b, hb))
        self.assertEqual(len(a), 256)
        c, hc = C.bucketed_digest([(5, 1), (6, 3)])
        self.assertEqual([i for i in range(256) if a[i] != c[i]], [6])
        self.assertEqual(len(C.bucketed_digest([(5, 1)], 64)[0]), 64)

    def test_golden_files_from_the_recorder(self):
        names = ("sample_host.cofr", "sample_client.cofr", "desync_host.cofr", "desync_client.cofr")
        trs = [read_golden(n) for n in names]
        self.assertEqual([t["header"]["role_name"] for t in trs], ["host", "client"] * 2)
        self.assertTrue(all(not t["truncated"] and not t["warnings"] for t in trs))
        self.assertEqual({r["name"] for t in trs[:2] for r in t["records"]} >= {"Meta", "Schema", "NetIn", "NetOut", "TxnApplied", "TxnCaptured", "Digest", "Marker", "Ownership"}, True)
        self.assertEqual([t["schema"].game for t in trs], ["example", "example", "toy", "toy"])
        self.assertEqual(trs[0]["meta"]["peer.1"], "1")
        a = A.align(trs[:2])
        self.assertEqual(len(a.lost), 0)
        self.assertEqual(len(a.orphans), 0)
        self.assertGreaterEqual(len(a.messages), 10)
        self.assertIsNone(A.find_divergence(a))     # the clean pair agrees on everything

    def test_golden_files_roundtrip_byte_for_byte(self):
        for n in ("sample_host.cofr", "sample_client.cofr", "desync_host.cofr", "desync_client.cofr"):
            data = read_bytes(os.path.join(GOLDEN, n))
            tr = C.loads(data)
            self.assertEqual(C.dumps(tr["header"], C.to_records(tr), tr["schema"]), data, n)

    def test_python_recomputes_the_digests_the_cpp_recorder_wrote(self):
        # the bucket hashes and the digest hash in the golden files were computed by the C++ recorder from the entries
        # that the detail records list; Python must get the same numbers
        for n in ("sample_host.cofr", "sample_client.cofr", "desync_host.cofr", "desync_client.cofr"):
            tr = read_golden(n)
            digests = [r for r in tr["records"] if r["type"] == C.T_DIGEST]
            main = [r for r in digests if r["bucketed"] and not r["detail"]][-1]
            entries = {}
            for r in digests:
                if r["detail"]:
                    entries.update(r["keys"])
            self.assertEqual(len(entries), main["item_count"], n)
            self.assertEqual(C.bucketed_digest(entries.items()), (main["shards"], main["hash"]), n)

    def test_golden_desync_pair_is_narrowed_to_bucket_key_and_value(self):
        trs = [read_golden("desync_host.cofr"), read_golden("desync_client.cofr")]
        a = A.align(trs)
        d = A.find_divergence(a)
        key = C.hash64(b"stage.q1")     # the same hash the C++ test used to name the key
        self.assertEqual(d["kind"], "digest")
        self.assertEqual(d["diff_keys"], ["0x%016X" % key])
        self.assertEqual(d["key"], "world:0x%016X" % key)             # the toy schema calls category 0 "world"
        nw = d["narrowing"]
        self.assertEqual(nw["buckets"], [key % 256])
        k = nw["keys"][0]
        self.assertEqual((k["bucket"], k["values"], k["texts"]), (key % 256, {0: 10, 1: 99}, {0: "stage.q1 = 10", 1: "stage.q1 = 99"}))
        names = [e["rec"]["name"] for e in d["chain"]["records"]]
        self.assertIn("ScriptWrite", names)                           # a game-defined record in the causal chain
        self.assertIn("TxnApplied", names)
        text = A.format_divergence(a, d)
        self.assertIn("stage.q1 = 99", text)
        self.assertIn("ScriptWrite", text)

    def test_truncated_tail_is_tolerated(self):
        tr = scenario()[0]
        data = C.dumps(tr["header"], [dict(r) for r in tr["records"]])
        for cut in (1, 3, 7):
            t2 = C.loads(data[:-cut])
            self.assertTrue(t2["truncated"])
            self.assertEqual(len(t2["records"]), len(tr["records"]) - 1)
            self.assertTrue(any("middle of a record" in w for w in t2["warnings"]))

    def test_bad_files(self):
        with self.assertRaises(C.CofrError):
            C.loads(b"XXXX" + bytes(80))
        with self.assertRaises(C.CofrError):
            C.loads(b"ABCD" + bytes([1, 0, 64, 0]) + bytes(80))        # another format's magic
        good = C.dumps({"slot": 1}, [])
        bad = bytearray(good)
        bad[4] = 2
        with self.assertRaises(C.CofrError):
            C.loads(bytes(bad))
        with self.assertRaises(C.CofrError):
            C.loads(good[:10])
        with self.assertRaises(C.CofrError):
            C.loads(good[:40])
        self.assertEqual(C.loads(good)["records"], [])
        self.assertEqual(len(good), C.HEADER_SIZE)

    def test_malformed_body_is_kept(self):
        h = {"slot": 1}
        marker = C.dumps(h, [{"type": 8, "mono_us": 5, "frame": 0, "kind": 0, "text": "ok"}])[C.HEADER_SIZE:]
        broken = struct.pack("<BBHIQ", 3, 0, 5, 0, 0) + b"\x00" * 5     # a NetIn whose body is too short for its fields
        tr = C.loads(C.dumps(h, []) + broken + marker)
        self.assertEqual(len(tr["records"]), 2)
        self.assertTrue(tr["records"][0].get("malformed"))
        self.assertEqual(tr["records"][1]["name"], "Marker")
        self.assertTrue(any("malformed" in w for w in tr["warnings"]))

    def test_pretty(self):
        text = C.pretty(scenario()[0], types={"digest"})
        self.assertIn("Digest", text)
        self.assertNotIn("NetIn", text)
        self.assertIn("role=host", text)
        self.assertEqual(C.pretty(scenario()[0], limit=2).count("\n"), 4)


class SchemaTests(unittest.TestCase):
    CUSTOM = {"game": "toy", "digest_categories": {"0": "world"}, "message_types": {"4": "batch"}, "txn_messages": [4],
              "custom_records": {"40": {"name": "Write", "fields": [
                  {"name": "a", "type": "u8"}, {"name": "b", "type": "u16"}, {"name": "c", "type": "u32"}, {"name": "d", "type": "u64"},
                  {"name": "e", "type": "i8"}, {"name": "f", "type": "i16"}, {"name": "g", "type": "i32"}, {"name": "h", "type": "i64"},
                  {"name": "i", "type": "f32"}, {"name": "j", "type": "f64"}, {"name": "k", "type": "str16"}, {"name": "l", "type": "bytes16"},
                  {"name": "m", "type": "bytes"}]}}}

    def test_default_schema_file_matches_the_code(self):
        with open(os.path.join(SCHEMAS, "default.json"), encoding="utf-8") as f:
            self.assertEqual(json.load(f), S.default().to_dict())

    def test_default_schema_matches_the_one_the_recorder_embeds(self):
        tr = read_golden("sample_host.cofr")
        recorded = [r for r in tr["records"] if r["type"] == C.T_SCHEMA][0]
        self.assertEqual(json.loads(recorded["json"]), S.default().to_dict())

    def test_example_game_schema_is_valid(self):
        s = S.load(os.path.join(SCHEMAS, "example_game.json"))
        self.assertTrue(s.custom_records)
        self.assertEqual(S.from_json(s.to_json()).to_dict(), s.to_dict())

    def test_present_keys_replace_missing_keys_keep_the_default(self):
        s = S.Schema({"digest_categories": {"0": "world"}})
        self.assertEqual(s.category(0), "world")
        self.assertEqual(s.category(2), "cat2")                  # the table was replaced, not merged
        self.assertEqual(s.marker_kind(1), "desync")             # not mentioned: default kept
        self.assertEqual(s.own_op(0), "grant")
        self.assertEqual(s.flag_names(2 | 8), ["repair", "catch-up"])
        self.assertTrue(s.is_txn_message(99))                    # txn_messages missing: every message counts
        self.assertFalse(S.Schema({"txn_messages": [4]}).is_txn_message(5))

    def test_bad_schemas_are_refused(self):
        for bad in ({"digest_categories": [1]}, {"digest_categories": {"x": "a"}}, {"ownership_owner_ops": "0"}, {"restate_mask": 300},
                    {"custom_records": {"3": {"name": "x"}}}, {"custom_records": {"40": {"fields": []}}},
                    {"custom_records": {"40": {"name": "x", "fields": [{"name": "a", "type": "u128"}]}}},
                    {"custom_records": {"40": {"name": "x", "fields": [{"name": "a", "type": "u8"}, {"name": "a", "type": "u8"}]}}},
                    {"custom_records": {"40": {"name": "x", "fields": [{"name": "r", "type": "bytes"}, {"name": "a", "type": "u8"}]}}},
                    [1, 2]):
            with self.assertRaises(S.SchemaError, msg=str(bad)):
                S.Schema(bad)
        with self.assertRaises(S.SchemaError):
            S.from_json("{not json")

    def test_every_field_type_round_trips(self):
        s = S.Schema(self.CUSTOM)
        vals = {"a": 255, "b": 65535, "c": 4294967295, "d": (1 << 64) - 1, "e": -128, "f": -32768, "g": -2, "h": -(1 << 63), "i": 0.5, "j": -2.25,
                "k": "héllo", "l": b"\x00\xff", "m": b"tail"}
        body = S.encode_custom(s.custom_records[40], vals)
        self.assertEqual(S.decode_custom(s.custom_records[40], body), vals)
        with self.assertRaises(S.ShortBody):
            S.decode_custom(s.custom_records[40], body[:5])

    def test_custom_records_are_decoded_and_named_through_the_schema(self):
        s = S.Schema(self.CUSTOM)
        body = S.encode_custom(s.custom_records[40], {"a": 1, "k": "x"})
        data = C.dumps({"slot": 0}, [{"type": 40, "mono_us": 1, "frame": 0, "payload": body}], s)
        tr = C.loads(data)                                         # no schema record in the file: the default knows nothing of type 40
        self.assertEqual(tr["records"][0]["name"], "Unknown40")
        tr = C.loads(data, schema=s)                               # an external schema overrides
        self.assertEqual((tr["records"][0]["name"], tr["records"][0]["fields"]["k"]), ("Write", "x"))
        short = C.dumps({"slot": 0}, [{"type": 40, "mono_us": 1, "frame": 0, "payload": b"\x01"}], s)
        tr = C.loads(short, schema=s)
        self.assertTrue(tr["records"][0].get("malformed"))
        self.assertTrue(any("shorter than its schema" in w for w in tr["warnings"]))

    def test_schema_in_the_file_is_used_and_an_unusable_one_falls_back(self):
        tb = TB(0, schema=S.Schema(self.CUSTOM))
        tb.digest(5, 0, 1, 1, shards=[1])
        tr = tb.trace()
        self.assertEqual(tr["schema"].game, "toy")
        self.assertIn("world epoch=1", C.describe(tr["records"][-1], tr["schema"]))
        raw = C.dumps(tb.h, [{"type": 9, "mono_us": 0, "frame": 0, "json": "{not json"}])
        tr = C.loads(raw)
        self.assertEqual(tr["schema"].game, "example")
        self.assertTrue(any("schema record" in w for w in tr["warnings"]))

    def test_names_come_from_the_schema_in_the_analysis(self):
        sch = S.Schema({"digest_categories": {"0": "world"}, "message_types": {"4": "batch"}})
        tb = [TB(0, schema=sch), TB(1, schema=sch)]
        tb[0].digest(10, 0, 3, 1, keys={7: 1})
        tb[1].digest(10, 0, 3, 2, keys={7: 2})
        a = A.align([t.trace() for t in tb])
        d = A.find_divergence(a)
        self.assertEqual(d["key"], "world:0x0000000000000007")
        self.assertIn("world digest", d["detail"])


class AlignTests(unittest.TestCase):
    def test_clock_offset_and_matching(self):
        a = A.align(scenario())
        self.assertEqual(a.slots, [0, 1, 2])
        self.assertEqual(a.ref_slot, 0)
        self.assertAlmostEqual(a.offset_us[2], 500000, delta=1000)
        self.assertLess(abs(a.offset_us[1]), 1000)
        self.assertEqual(len(a.lost), 0)
        self.assertEqual(len(a.orphans), 0)
        # 4 txn batches + 4 acks, per client
        self.assertEqual(len(a.messages), 16)

    def test_lost_and_duplicate(self):
        a = A.align(scenario(lost={(2, 2)}, dup_seq=4))
        self.assertEqual(len(a.lost), 1)
        self.assertEqual(a.lost[0][:2], (0, 2))
        self.assertEqual(len(a.duplicates), 1)
        self.assertEqual(a.duplicates[0][:2], (0, 1))
        self.assertIn("lost: 1", A.format_alignment(a))

    def test_transport_peer_ids_are_mapped_to_slots_by_meta(self):
        m1 = bytes([0xC0, 2, 5, 2, 0, 9, 2, 0, 0, 0, 0, 0])
        m2 = bytes([0xC0, 4, 5, 4, 0, 9, 1, 1, 1, 1, 1, 1])
        h, c = TB(0, meta={"peer.7": "2"}), TB(2)
        h.net(True, 10, 7, 2, 0, m1)            # the host sent to transport peer 7, which is machine slot 2
        h.net(True, 20, 7, 4, 1, m2)
        c.net(False, 15, 0, 2, 0, m1)           # the client sees the host as peer 0 (the same number as its slot)
        c.net(False, 25, 0, 4, 1, m2)
        c.net(True, 30, 0, 5, 1, m2[::-1])
        h.net(False, 35, 7, 5, 1, m2[::-1])
        a = A.align([h.trace(), c.trace()])
        self.assertEqual((len(a.messages), len(a.lost), len(a.orphans)), (3, 0, 0))
        self.assertEqual({(m["from"], m["to"]) for m in a.messages}, {(0, 2), (2, 0)})
        # without the Meta entry the host's peer 7 means slot 7: nothing matches
        h2 = TB(0)
        h2.net(True, 10, 7, 2, 0, m1)
        a = A.align([h2.trace(), c.trace()])
        self.assertEqual(len(a.messages), 0)

    def test_orphan_input(self):
        t0, t1 = TB(0), TB(1)
        t0.add(C.T_MARKER, 1, kind=0, text="x")
        t1.net(False, 50, 0, 4, 99, b"\x04\x63\x00")  # arrived from slot 0, slot 0 never sent it
        a = A.align([t0.trace(), t1.trace()])
        self.assertEqual(len(a.orphans), 1)

    def test_duplicate_slot_and_dropped_notes(self):
        t = scenario()
        t[1]["header"]["slot"] = 2
        t[0]["header"]["records_dropped"] = 5
        a = A.align(t)
        self.assertEqual(len(a.slots), 3)
        self.assertTrue(any("two traces claim slot 2" in x for x in a.anomalies))
        self.assertTrue(any("lost 5 old records" in x for x in a.anomalies))

    def test_four_machines(self):
        tb = [TB(s) for s in range(4)]
        for s in range(4):
            tb[s].txn(C.T_TXN_APPLIED, 100, 1, 7)
        tb[3].txn(C.T_TXN_APPLIED, 200, 2, 9)
        tb[0].txn(C.T_TXN_APPLIED, 200, 2, 8)
        tb[1].txn(C.T_TXN_APPLIED, 200, 2, 8)
        tb[2].txn(C.T_TXN_APPLIED, 200, 2, 8)
        d = A.find_divergence(A.align([t.trace() for t in tb]))
        self.assertEqual((d["kind"], d["suspects"], d["slots"]), ("txn-hash", [3], [0, 1, 2, 3]))


class DivergenceTests(unittest.TestCase):
    def test_clean_run_has_no_divergence(self):
        a = A.align(scenario(digest2="same", clean_extras=True, dup_seq=4))
        self.assertIsNone(A.find_divergence(a))
        self.assertIn("No divergence", A.format_divergence(a, None))

    def test_bad_txn_is_first_and_names_the_culprit(self):
        a = A.align(scenario(bad_seq=3, lost={(2, 2)}))
        d = A.find_divergence(a)
        self.assertEqual(d["kind"], "txn-hash")
        self.assertEqual(d["key"], "txn:3[0]")
        self.assertEqual(d["suspects"], [1])
        self.assertEqual(d["slots"], [0, 1, 2])
        direct = [e for e in d["chain"]["records"] if e["role"] == "direct"]
        self.assertTrue({0, 1, 2} <= {e["slot"] for e in direct})
        self.assertTrue(all(e["rec"].get("seq") == 3 for e in direct if e["rec"]["name"].startswith("Txn")))
        self.assertTrue(any("lost in transit" in n for n in d["chain"]["notes"]))
        self.assertTrue(any(c["kind"] == "digest" for c in d["also"]))
        ts = [e["aligned_us"] for e in d["chain"]["records"]]
        self.assertEqual(ts, sorted(ts))
        text = A.format_divergence(a, d)
        self.assertIn("FIRST DIVERGENCE (txn-hash)", text)
        self.assertIn("suspect slot(s): [1]", text)

    def test_digest_divergence_names_the_key_and_window(self):
        a = A.align(scenario())
        d = A.find_divergence(a)
        self.assertEqual(d["kind"], "digest")
        self.assertEqual(d["suspects"], [1])
        self.assertEqual(d["diff_keys"], ["0x0000000000000020"])
        self.assertEqual(d["key"], "story:0x0000000000000020")
        lo, hi = d["chain"]["window_us"]
        agree = max(a.t(s, r) for s in a.slots for r in a.traces[s]["records"] if r["type"] == C.T_DIGEST and r["seq"] == 1)
        self.assertEqual(lo, agree)
        self.assertEqual(hi, d["aligned_us"])
        for e in d["chain"]["records"]:
            self.assertGreaterEqual(e["aligned_us"], lo)
            self.assertLessEqual(e["aligned_us"], hi)

    def test_shard_level_digest(self):
        tb = [TB(0), TB(1)]
        tb[0].digest(10, 1, 3, 1, shards=[5, 6, 7])
        tb[1].digest(10, 1, 3, 2, shards=[5, 9, 7])
        d = A.find_divergence(A.align([t.trace() for t in tb]))
        self.assertEqual(d["diff_shards"], [1])
        self.assertEqual(d["key"], "actors:shard:1")
        self.assertEqual(d["narrowing"]["buckets"], [])           # not key buckets: shard 1 is not a bucket of keys

    def test_per_key_detail_records_and_entry_markers(self):
        key = 0xAA650F118B7CB748
        tb = [TB(0), TB(1)]
        for t, h in zip(tb, (11, 22)):
            t.add(C.T_DIGEST, 900, category=4, epoch=1, seq=0, hash=h, item_count=3, shards=[0] * 255 + [h], keys={}, bucketed=True)
        # detail records (flag bit2): the entries arrive split over two records on each machine
        for i, (t, val) in enumerate(zip(tb, (5, 77))):
            t.add(C.T_DIGEST, 901, category=4, epoch=1, seq=0, hash=0, item_count=3, shards=[], keys={0x10: 1, key: val}, detail=True)
            t.add(C.T_DIGEST, 902, category=4, epoch=1, seq=0, hash=0, item_count=3, shards=[], keys={0x20: 2}, detail=True)
            t.add(C.T_MARKER, 903, kind=0, text="entry %016x %d quest_stage intro = %d" % (key, val, val))
        d = A.find_divergence(A.align([t.trace() for t in tb]))
        self.assertEqual(d["kind"], "digest")
        self.assertEqual(d["diff_keys"], ["0x%016X" % key])
        self.assertEqual(d["diff_shards"], [255])
        self.assertIn("quest_stage intro = 5", d["detail"])
        self.assertIn("quest_stage intro = 77", d["detail"])
        self.assertEqual(C.loads(tb[0].data())["records"][2]["detail"], True)
        nw = d["narrowing"]
        self.assertEqual(nw["buckets"], [255])
        self.assertEqual([k["key"] for k in nw["keys"]], ["0x%016X" % key])
        k = nw["keys"][0]
        self.assertEqual(k["bucket"], key % 256)
        self.assertEqual(k["values"], {0: 5, 1: 77})
        self.assertIn("= 77", k["texts"][1])
        text = A.format_divergence(A.align([t.trace() for t in tb]), d)
        self.assertIn("narrowing: bucket(s) 255 of 256", text)
        self.assertIn("slot 1: value hash 77", text)
        self.assertIn("NOT in a differing bucket", text)    # the test's bucket 255 does not match key mod 256 (0x48)

    def test_story_bucket_is_narrowed_to_a_key_by_a_later_desync_dump(self):
        key = 0xAA650F118B7CB748
        tb = [TB(0), TB(1)]
        for t, h in zip(tb, (11, 22)):   # a story digest: buckets only, bucket 0x48 differs
            t.add(C.T_DIGEST, 100, category=0, epoch=1, seq=7, hash=h, item_count=3, shards=[0] * 0x48 + [h] + [0] * (255 - 0x48), keys={}, bucketed=True)
        for t, val in zip(tb, (0, 77)):   # later, the desync dump of the real world with key detail (and an extra identical key)
            t.add(C.T_DIGEST, 900, category=4, epoch=1, seq=0, hash=val + 1, item_count=2, shards=[0] * 0x48 + [val] + [0] * (255 - 0x48), keys={}, bucketed=True)
            t.add(C.T_DIGEST, 901, category=4, epoch=1, seq=0, hash=0, item_count=2, shards=[], keys={0x10: 1, 0x21: val + 1, key: val}, detail=True)
            t.add(C.T_MARKER, 903, kind=0, text="entry %016x %d quest_stage intro = %d" % (key, val, val))
        a = A.align([t.trace() for t in tb])
        cands = [c for c in A.find_all(a) if c["kind"] == "digest" and c["category"] == 0]
        self.assertEqual(len(cands), 1)
        nw = cands[0]["narrowing"]
        self.assertEqual(nw["buckets"], [0x48])
        self.assertEqual([k["key"] for k in nw["keys"]], ["0x%016X" % key])
        self.assertTrue(nw["keys"][0]["in_diff_bucket"])
        self.assertTrue(nw["key_source"].startswith("other digest"))   # category 4 (the desync dump) supplied the keys
        self.assertIn("= 77", nw["keys"][0]["texts"][1])

    def test_bucket_count_is_not_fixed_at_256(self):
        entries = [(k, k * 3) for k in range(40)]
        changed = [(k, v + (1 if k == 37 else 0)) for k, v in entries]
        tb = [TB(0), TB(1)]
        for t, ent in zip(tb, (entries, changed)):
            shards, h = C.bucketed_digest(ent, 16)
            t.add(C.T_DIGEST, 10, category=0, epoch=1, seq=1, hash=h, item_count=40, shards=shards, keys={}, bucketed=True)
            t.add(C.T_DIGEST, 11, category=0, epoch=1, seq=1, hash=0, item_count=40, shards=[], keys=dict(ent), detail=True)
        d = A.find_divergence(A.align([t.trace() for t in tb]))
        self.assertEqual(d["narrowing"]["buckets"], [37 % 16])
        self.assertEqual(d["diff_keys"], ["0x%016X" % 37])
        self.assertEqual(d["narrowing"]["keys"][0]["bucket"], 37 % 16)
        self.assertTrue(d["narrowing"]["keys"][0]["in_diff_bucket"])
        self.assertEqual(d["narrowing"]["bucket_count"], 16)

    def test_narrowing_without_key_detail_says_so(self):
        tb = [TB(0), TB(1)]
        tb[0].digest(10, 1, 3, 1, shards=[0] * 256, bucketed=True)
        tb[1].digest(10, 1, 3, 2, shards=[0] * 9 + [4] + [0] * 246, bucketed=True)
        d = A.find_divergence(A.align([t.trace() for t in tb]))
        self.assertEqual(d["narrowing"]["buckets"], [9])
        self.assertEqual(d["narrowing"]["keys"], [])
        self.assertIn("no per-key detail recorded", A.format_divergence(A.align([t.trace() for t in tb]), d))

    def test_host_commit_is_not_reported_as_a_missing_apply(self):
        tb = [TB(0), TB(1)]
        tb[0].txn(C.T_TXN_CAPTURED, 100, 1, 5)
        tb[1].txn(C.T_TXN_APPLIED, 150, 1, 5)
        tb[0].add(C.T_MARKER, 5_000_000, kind=0, text="late")   # the host's trace goes on for seconds
        a = A.align([t.trace() for t in tb])
        self.assertEqual([c for c in A.find_all(a) if c["kind"] == "txn-missing"], [])

    def test_earliest_wins_over_later(self):
        a = A.align(scenario(bad_seq=2))
        d = A.find_divergence(a)
        self.assertEqual(d["key"], "txn:2[0]")
        a = A.align(scenario(bad_seq=4))
        self.assertEqual(A.find_divergence(a)["key"], "txn:4[0]")  # digest at 700 is later than seq 4 at 400

    def test_ownership_conflict_and_stale(self):
        tb = [TB(0), TB(1), TB(2)]
        tb[0].own(100, 0, 5, 3, 255, 1)
        tb[2].own(110, 0, 5, 3, 255, 2)
        d = A.find_divergence(A.align([t.trace() for t in tb]))
        self.assertEqual(d["kind"], "ownership-conflict")
        self.assertEqual(d["suspects"], [1, 2])
        tb = [TB(0), TB(1)]
        tb[1].own(100, 0, 6, 4, 255, 1)
        tb[1].own(120, 1, 6, 3, 1, 0)
        d = A.find_divergence(A.align([t.trace() for t in tb]))
        self.assertEqual(d["kind"], "ownership-stale")
        self.assertEqual(d["suspects"], [1])
        # rejected stale records are the system working, not a divergence
        tb = [TB(0), TB(1)]
        tb[1].own(100, 0, 6, 4, 255, 1)
        tb[1].own(120, 3, 6, 3, 1, 0)
        tb[1].own(130, 4, 6, 3, 1, 0)
        tb[1].own(140, 5, 6, 2, 1, 0)
        tb[0].own(150, 5, 6, 1, 0, 2)
        self.assertIn("rejectedNonOwner", C.describe(tb[1].trace()["records"][-1]))
        self.assertIsNone(A.find_divergence(A.align([t.trace() for t in tb])))

    def test_which_ownership_ops_count_comes_from_the_schema(self):
        sch = S.Schema({"ownership_owner_ops": [1]})          # only a transfer sets an owner in this game
        tb = [TB(0, schema=sch), TB(1, schema=sch)]
        tb[0].own(100, 0, 5, 3, 255, 0)
        tb[1].own(110, 0, 5, 3, 255, 1)                       # two grants at one epoch: not an owner op here
        self.assertIsNone(A.find_divergence(A.align([t.trace() for t in tb])))
        tb[0].own(120, 1, 5, 4, 0, 0)
        tb[1].own(130, 1, 5, 4, 0, 1)
        self.assertEqual(A.find_divergence(A.align([t.trace() for t in tb]))["kind"], "ownership-conflict")

    def test_which_applies_restate_state_comes_from_the_schema(self):
        def pair(schema):
            tb = [TB(0, schema=schema), TB(1, schema=schema)]
            tb[0].txn(C.T_TXN_APPLIED, 100, 1, 5)
            tb[1].txn(C.T_TXN_APPLIED, 100, 1, 6, flags=2)    # flag bit 2 is "repair" in the default schema
            return A.find_divergence(A.align([t.trace() for t in tb]))
        self.assertIsNone(pair(None))
        self.assertEqual(pair(S.Schema({"restate_mask": 0}))["kind"], "txn-hash")

    def test_desync_marker_is_reported_with_its_actor_history(self):
        tb = [TB(0), TB(1)]
        tb[0].own(100, 1, 0x100A, 16, 1, 0)
        tb[0].own(200, 1, 0x100A, 22, 0, 1)
        tb[0].own(210, 1, 0x200B, 3, 0, 1)
        tb[1].add(C.T_MARKER, 900, kind=1, text="stale_applied: update at epoch 11 accepted: ref=#100a epoch=11")
        tb[1].add(C.T_MARKER, 910, kind=1, text="stale_applied: again: ref=#100a")
        d = A.find_divergence(A.align([t.trace() for t in tb]))
        self.assertEqual((d["kind"], d["suspects"], d["key"]), ("desync-marker", [1], "marker:stale_applied"))
        self.assertEqual(d["total_candidates"], 1)   # the repeat is folded
        direct = [e["rec"]["ref"] for e in d["chain"]["records"] if e["role"] == "direct" and e["rec"]["type"] == C.T_OWNERSHIP]
        self.assertEqual(direct, ["actor:100A", "actor:100A"])
        self.assertIn("slot 1 reported", d["detail"])

    def test_game_defined_record_naming_the_seq_is_part_of_the_chain(self):
        sch = S.Schema({"custom_records": {"40": {"name": "Script", "fields": [{"name": "seq", "type": "u64"}]}}})
        tb = [TB(0, schema=sch), TB(1, schema=sch)]
        tb[0].txn(C.T_TXN_APPLIED, 100, 5, 1)
        tb[1].txn(C.T_TXN_APPLIED, 100, 5, 2)
        tb[1].add(40, 101, fields={"seq": 5})
        tb[1].add(40, 102, fields={"seq": 99})
        d = A.find_divergence(A.align([t.trace() for t in tb]))
        scripts = [(e["role"], e["rec"]["fields"]["seq"]) for e in d["chain"]["records"] if e["rec"]["name"] == "Script"]
        self.assertEqual(sorted(scripts), [("context", 99), ("direct", 5)])

    def test_only_the_schemas_transaction_messages_are_direct_in_the_chain(self):
        def chain(schema):
            tb = [TB(0, schema=schema), TB(1, schema=schema)]
            tb[0].txn(C.T_TXN_APPLIED, 100, 5, 1)
            tb[1].txn(C.T_TXN_APPLIED, 100, 5, 2)
            tb[0].net(True, 90, 1, 4, 5, b"\x04\x05\x01")
            tb[1].net(False, 95, 0, 4, 5, b"\x04\x05\x01")
            tb[0].net(True, 91, 1, 9, 5, b"\x09\x05\x01")
            tb[1].net(False, 96, 0, 9, 5, b"\x09\x05\x01")
            d = A.find_divergence(A.align([t.trace() for t in tb]))
            return sorted({e["rec"]["msg_type"] for e in d["chain"]["records"] if e["role"] == "direct" and e["rec"]["name"].startswith("Net")})
        self.assertEqual(chain(None), [4, 9])
        self.assertEqual(chain(S.Schema({"txn_messages": [4]})), [4])

    def test_double_apply(self):
        tb = [TB(0), TB(1)]
        for t in (100, 110):
            tb[1].txn(C.T_TXN_APPLIED, t, 5, 9)
        tb[0].txn(C.T_TXN_APPLIED, 90, 5, 9)
        d = A.find_divergence(A.align([t.trace() for t in tb]))
        self.assertEqual(d["kind"], "txn-double")
        self.assertEqual(d["suspects"], [1])

    def test_missing_txn_needs_a_gap_or_grace(self):
        tb = [TB(0), TB(1)]
        tb[0].txn(C.T_TXN_APPLIED, 100, 5, 9)
        tb[0].txn(C.T_TXN_APPLIED, 200, 6, 9)
        tb[1].txn(C.T_TXN_APPLIED, 210, 6, 9)
        d = A.find_divergence(A.align([t.trace() for t in tb]))
        self.assertEqual((d["kind"], d["key"], d["suspects"]), ("txn-missing", "txn:5", [1]))
        # no later seq, and the trace ends within the grace time: just lag, not a bug
        tb = [TB(0), TB(1)]
        tb[0].txn(C.T_TXN_APPLIED, 100, 5, 9)
        tb[1].add(C.T_MARKER, 900, kind=0, text="x")
        self.assertIsNone(A.find_divergence(A.align([t.trace() for t in tb])))
        # same, but the machine kept recording well past the grace time
        tb[1].add(C.T_MARKER, 3500, kind=0, text="x")
        d = A.find_divergence(A.align([t.trace() for t in tb]))
        self.assertEqual(d["kind"], "txn-missing")
        self.assertIn("no apply within", d["detail"])


class ShrinkTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def fixture(self, n=120, with_dup=True):
        steps = [{"op": "deliver", "to": 1 + (i % 2), "from": 0, "hex": "01%02x" % (i % 200)} for i in range(n)]
        steps[n // 7] = {"op": "deliver", "to": 1, "from": 0, "hex": "ee01"}
        steps[n * 5 // 6] = {"op": "deliver", "to": 1, "from": 0, "hex": "ff01"}
        if with_dup:
            steps[n // 3] = {"op": "inject", "kind": "dup", "slot": 2}
        steps.append({"op": "quiesce", "pin": True})
        return {"version": 1, "config": {"seed": 3, "clients": 2}, "steps": steps}

    def test_ddmin_finds_exact_subset(self):
        need = {3, 77, 150}
        calls = []

        def fails(sel):
            calls.append(len(sel))
            return need <= set(sel)
        kept, runs, complete = SH.ddmin(300, fails)
        self.assertEqual(sorted(kept), sorted(need))
        self.assertTrue(complete)
        self.assertLess(runs, 150)

    def test_ddmin_budget_and_trivial(self):
        kept, runs, complete = SH.ddmin(300, lambda sel: {3, 77} <= set(sel), max_runs=5)
        self.assertFalse(complete)
        self.assertEqual(runs, 5)
        self.assertEqual(SH.ddmin(10, lambda sel: True)[0], [])
        self.assertEqual(SH.ddmin(0, lambda sel: True)[0], [])

    @slow
    def test_shrink_toy_to_two_steps_plus_pin(self):
        orc = SH.CommandOracle(REPLAY, tmpdir=self.tmp)
        out = SH.shrink_fixture(self.fixture(n=30), orc)
        ops = [(s["op"], s.get("hex")) for s in out["steps"]]
        self.assertEqual(ops, [("deliver", "ee01"), ("deliver", "ff01"), ("quiesce", None)])
        self.assertEqual(out["shrunk"]["original_steps"], 31)
        self.assertEqual(out["shrunk"]["reduced_steps"], 3)
        self.assertEqual(out["shrunk"]["signature"], "stale echo applied on slot #")
        self.assertTrue(out["shrunk"]["complete"])
        self.assertEqual(out["shrunk"]["violations"], ["stale echo applied on slot 1"])
        self.assertEqual(os.listdir(self.tmp), [])  # temp fixtures cleaned up
        # the fixture also holds the "dup" bug, a different failure; the shrink must keep the original one
        self.assertFalse(any(s.get("op") == "inject" for s in out["steps"]))

    def test_python_function_hook_shrinks_the_same_way(self):
        orc = SH.PyOracle("toy_replay:replay", path=SRC)
        out = SH.shrink_fixture(self.fixture(), orc)
        self.assertEqual([s.get("hex") for s in out["steps"]], ["ee01", "ff01", None])
        self.assertEqual(out["shrunk"]["signature"], "stale echo applied on slot #")
        self.assertGreater(orc.runs, 5)

    def test_python_hook_errors_are_reported(self):
        with self.assertRaises(SH.OracleError):
            SH.PyOracle("no_such_module_xyz:f")
        with self.assertRaises(SH.OracleError):
            SH.PyOracle("toy_replay_without_colon")
        with self.assertRaises(SH.OracleError):
            SH.PyOracle("toy_replay:replay", path=SRC)({"version": 2, "steps": []})        # the hook raises on a bad fixture
        orc = SH.PyOracle("json:dumps")                                                     # returns a string, not a result dict
        with self.assertRaises(SH.OracleError):
            orc({"a": 1})

    def test_pinned_steps_survive(self):
        def orc(fx):
            ops = [(s.get("hex")) for s in fx["steps"]]
            bad = "ee01" in ops and "ff01" in ops
            return {"diverged": bad, "violations": ["x"] if bad else []}
        out = SH.shrink_fixture(self.fixture(with_dup=False), orc)
        self.assertEqual(out["steps"][-1], {"op": "quiesce", "pin": True})
        self.assertEqual(len(out["steps"]), 3)

    def test_a_named_list_can_be_shrunk(self):
        fx = {"events": [{"v": "x%d" % i} for i in range(20)]}

        def orc2(f):
            vals = [e["v"] for e in f["events"]]
            return {"diverged": "x7" in vals and "x9" in vals, "violations": ["broke"]}
        out = SH.shrink_fixture(fx, orc2, list_key="events")
        self.assertEqual([e["v"] for e in out["events"]], ["x7", "x9"])
        self.assertEqual(out["shrunk"]["list_key"], "events")
        with self.assertRaises(SH.OracleError):
            SH.shrink_fixture(fx, orc2, list_key="nothing")

    @slow
    def test_budget_marks_incomplete(self):
        out = SH.shrink_fixture(self.fixture(n=30), SH.CommandOracle(REPLAY, tmpdir=self.tmp), max_runs=4)
        self.assertFalse(out["shrunk"]["complete"])
        self.assertGreater(out["shrunk"]["reduced_steps"], 3)

    @slow
    def test_nothing_to_shrink_and_errors(self):
        fx = self.fixture(with_dup=False)
        fx["steps"] = [s for s in fx["steps"] if s.get("hex") != "ff01"]
        with self.assertRaises(SH.OracleError):
            SH.shrink_fixture(fx, SH.CommandOracle(REPLAY, tmpdir=self.tmp))
        with self.assertRaises(SH.OracleError):
            SH.CommandOracle(REPLAY, tmpdir=self.tmp)({"version": 2, "steps": []})   # replay exits 2
        with self.assertRaises(SH.OracleError):
            SH.CommandOracle([sys.executable, "-I", TOY])                              # no {fixture}
        with self.assertRaises(SH.OracleError):
            SH.CommandOracle(["definitely-not-a-program-xyz", "{fixture}"], tmpdir=self.tmp)({"version": 1, "steps": []})

    @slow
    def test_violation_line_contract_shrinks_via_ops(self):
        fx = self.fixture(n=30)
        sim = {"format": "scenario", "seed": 5, "machines": 3, "ops": fx["steps"]}
        cmd = [sys.executable, "-I", TOY, "--lines", "{fixture}"]
        out = SH.shrink_fixture(sim, SH.CommandOracle(cmd, tmpdir=self.tmp))
        self.assertNotIn("steps", out)
        self.assertEqual([o.get("hex") for o in out["ops"]], ["ee01", "ff01", None])
        self.assertEqual(out["shrunk"]["signature"], "stale_echo_applied")
        self.assertEqual(out["format"], "scenario")
        paths = G.generate(out, "sim case", self.tmp, target="my_fuzzer", flag="--replay ")
        with open(paths[1]) as f:
            cm = f.read()
        self.assertIn("my_fuzzer", cm)
        self.assertIn("--replay", cm)
        self.assertIn("Steps: 3", cm)

    def test_signature_normalises_numbers(self):
        r = {"diverged": True, "violations": ["actor 0xDEADBEEF dup on slot 3 hash 0123456789abcdef"]}
        self.assertEqual(SH.signature(r), "actor # dup on slot # hash #")
        self.assertEqual(SH.signature({"diverged": True, "first": {"category": "story"}}), "diverged:story")
        self.assertIsNone(SH.signature({"diverged": False}))

    def test_fixture_from_traces(self):
        trs = scenario(bad_seq=3)
        # one truncated datagram is skipped and counted
        tb = TB(1)
        tb.net(False, 5, 0, 4, 1, b"\x04\x01\x01", flags=1)
        trs[1]["records"] += [dict(r, idx=999 + i) for i, r in enumerate(C.loads(tb.data())["records"])]
        fx = SH.fixture_from_traces(trs)
        deliver = [s for s in fx["steps"] if s["op"] == "deliver"]
        n_in = sum(1 for t in trs for r in t["records"] if r["type"] == C.T_NET_IN and not r["truncated"])
        self.assertEqual(len(deliver), n_in)
        self.assertEqual(fx["source"]["skipped_steps"], 1)
        self.assertEqual([s for s in fx["steps"] if s["op"] not in ("deliver", "quiesce")], [])
        self.assertEqual(fx["steps"][-1], {"op": "quiesce", "pin": True})
        ts = [s["t"] for s in fx["steps"] if "t" in s]
        self.assertEqual(ts, sorted(ts))
        self.assertEqual(fx["config"]["clients"], 2)
        self.assertEqual(bytes.fromhex(deliver[0]["hex"])[0] in (4, 5), True)


@slow
class GentestTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def shrunk(self):
        fx = ShrinkTests("test_ddmin_budget_and_trivial").fixture(n=20, with_dup=False)
        fx["steps"] = [fx["steps"][0], {"op": "deliver", "to": 1, "from": 0, "hex": "ee01"},
                       {"op": "deliver", "to": 1, "from": 0, "hex": "ff01"}, fx["steps"][-1]]
        fx["shrunk"] = {"signature": "stale echo applied on slot #"}
        return fx

    def test_generate_and_run(self):
        paths = G.generate(self.shrunk(), "Stale Echo!", self.tmp)
        self.assertEqual([os.path.basename(p) for p in paths], ["stale_echo.json", "stale_echo.cmake"])
        with open(paths[0]) as f:
            fx = json.load(f)
        self.assertEqual(fx["expect"], {"converges": True, "bug_signature": "stale echo applied on slot #"})
        with open(paths[1]) as f:
            cm = f.read()
        self.assertIn("add_test(NAME cofr_stale_echo", cm)
        self.assertIn("replay_tool", cm)
        self.assertEqual(G.safe_name("../../x y"), "x_y")
        self.assertEqual(G.safe_name("!!!"), "case")
        # the bug is still present in the toy, so the regression test must FAIL (it guards a bug that is not fixed yet)
        with contextlib.redirect_stdout(io.StringIO()):
            n, bad = RG.run_dir(self.tmp, SH.CommandOracle(REPLAY, tmpdir=self.tmp))
        self.assertEqual((n, bad), (1, 1))

    def test_regress_expectations(self):
        d = self.tmp
        good = {"version": 1, "steps": [{"op": "quiesce"}], "expect": {"converges": True}}
        known_bad = dict(self.shrunk(), expect={"converges": False})
        for name, fx in (("a_good", good), ("b_known_bad", known_bad)):
            with open(os.path.join(d, name + ".json"), "w") as f:
                json.dump(fx, f)
        with contextlib.redirect_stdout(io.StringIO()):
            n, bad = RG.run_dir(d, SH.CommandOracle(REPLAY, tmpdir=d))
            self.assertEqual((n, bad), (2, 0))
            self.assertEqual(RG.main([d, "--replay-cmd", subprocess.list2cmdline(REPLAY), "--tmpdir", d]), 0)
            self.assertEqual(RG.main([d, "--replay-py", "toy_replay:replay", "--replay-path", SRC]), 0)


class ReportTests(unittest.TestCase):
    def test_report_content_and_escaping(self):
        evil = "<script>alert(1)</script>"
        html = R.render(scenario(bad_seq=3, instance1=evil), {"steps": [{"op": "deliver", "hex": "<u>"}],
                                                              "shrunk": {"original_steps": 9, "reduced_steps": 1, "oracle_runs": 4, "signature": "<i>x"}})
        self.assertNotIn("<script>", html)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", html)
        self.assertNotIn("<u>", html)
        self.assertNotIn("<i>x", html)
        self.assertIn("First divergence", html)
        self.assertIn("txn:3", html)
        self.assertIn("<svg", html)
        self.assertIn("Minimal reproduction", html)
        self.assertNotIn("http://", html.replace("http://www.w3.org", ""))
        self.assertTrue(html.startswith("<!doctype html>"))

    def test_report_shows_the_narrowing(self):
        key = 0xAA650F118B7CB748
        tb = [TB(0), TB(1)]
        for t, val in zip(tb, (0, 77)):
            t.add(C.T_DIGEST, 900, category=4, epoch=1, seq=0, hash=val + 1, item_count=1, shards=[0] * 0x48 + [val] + [0] * (255 - 0x48), keys={}, bucketed=True)
            t.add(C.T_DIGEST, 901, category=4, epoch=1, seq=0, hash=0, item_count=1, shards=[], keys={key: val}, detail=True)
            t.add(C.T_MARKER, 903, kind=0, text="entry %016x %d quest_stage intro = <b>%d" % (key, val, val))
        html = R.render([t.trace() for t in tb])
        self.assertIn("Narrowing: digest, bucket, key, value", html)
        self.assertIn("0xAA650F118B7CB748", html)
        self.assertIn('<td class="m">quest_stage intro = &lt;b&gt;77</td>', html)
        self.assertNotIn("<b>77", html)

    def test_report_of_the_golden_desync_pair(self):
        html = R.render([read_golden("desync_host.cofr"), read_golden("desync_client.cofr")])
        self.assertIn("stage.q1 = 99", html)
        self.assertIn("ScriptWrite", html)

    def test_clean_report(self):
        html = R.render(scenario(digest2="same"))
        self.assertIn("No divergence found", html)
        self.assertNotIn("Minimal reproduction", html)


@slow
class CliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_cli(self, *args):
        p = subprocess.run([sys.executable, "-I", os.path.join(SRC, "flight.py")] + list(args), capture_output=True, text=True, errors="replace")
        return p.returncode, p.stdout + p.stderr

    def test_end_to_end(self):
        files = []
        for tr in scenario(bad_seq=3):
            p = os.path.join(self.tmp, "s%d.cofr" % tr["header"]["slot"])
            C.dump(p, tr["header"], [dict(r) for r in tr["records"]])
            files.append(p)
        rc, out = self.run_cli("print", files[0], "--type", "digest")
        self.assertEqual(rc, 0)
        self.assertIn("Digest", out)
        rc, out = self.run_cli("align", *files)
        self.assertIn("slots: [0, 1, 2]", out)
        rc, out = self.run_cli("diverge", *files, "--check")
        self.assertEqual(rc, 1)
        self.assertIn("FIRST DIVERGENCE (txn-hash)", out)
        rc, out = self.run_cli("diverge", *files, "--json")
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out)["key"], "txn:3[0]")
        fx = os.path.join(self.tmp, "fx.json")
        rc, out = self.run_cli("fixture", *files, "-o", fx)
        self.assertEqual(rc, 0, out)
        # a hand-made failing fixture for the shrinker (the toy replay does not understand real datagrams)
        toyfx = ShrinkTests("test_ddmin_budget_and_trivial").fixture(n=30, with_dup=False)
        with open(fx, "w") as f:
            json.dump(toyfx, f)
        sh = os.path.join(self.tmp, "sh.json")
        rc, out = self.run_cli("shrink", fx, "--replay-cmd", subprocess.list2cmdline(REPLAY), "-o", sh, "--tmpdir", self.tmp)
        self.assertEqual(rc, 0, out)
        self.assertIn("-> 3 steps", out)
        sh2 = os.path.join(self.tmp, "sh2.json")
        rc, out = self.run_cli("shrink", fx, "--replay-py", "toy_replay:replay", "--replay-path", SRC, "-o", sh2)
        self.assertEqual(rc, 0, out)
        self.assertIn("-> 3 steps", out)
        rd = os.path.join(self.tmp, "reg")
        rc, out = self.run_cli("gentest", sh, "--name", "echo", "--out", rd)
        self.assertEqual(rc, 0, out)
        self.assertTrue(os.path.exists(os.path.join(rd, "echo.json")))
        rc, out = self.run_cli("regress", rd, "--replay-cmd", subprocess.list2cmdline(REPLAY), "--tmpdir", self.tmp)
        self.assertEqual(rc, 1)  # bug still present in the toy
        self.assertIn("FAIL echo.json", out)
        rep = os.path.join(self.tmp, "r.html")
        rc, out = self.run_cli("report", *files, "-o", rep, "--shrink", sh)
        self.assertEqual(rc, 0, out)
        with open(rep, encoding="utf-8") as f:
            self.assertIn("Minimal reproduction", f.read())
        rc, out = self.run_cli("diverge", files[0])
        self.assertNotEqual(rc, 0)
        self.assertIn("at least 2 traces", out)
        rc, out = self.run_cli("print", os.path.join(self.tmp, "nope.cofr"))
        self.assertNotEqual(rc, 0)

    def test_schema_command_and_option(self):
        rc, out = self.run_cli("schema")
        self.assertEqual(rc, 0)
        self.assertEqual(json.loads(out), S.default().to_dict())
        rc, out = self.run_cli("schema", os.path.join(SCHEMAS, "example_game.json"))
        self.assertEqual(rc, 0)
        self.assertIn("ScriptWrite", out)
        bad = os.path.join(self.tmp, "bad.json")
        with open(bad, "w") as f:
            f.write("{nope")
        rc, out = self.run_cli("schema", bad)
        self.assertNotEqual(rc, 0)
        self.assertIn("not valid JSON", out)
        # --schema overrides what the files say
        sch = os.path.join(self.tmp, "world.json")
        with open(sch, "w") as f:
            json.dump({"digest_categories": {"0": "mapstate"}}, f)
        host, cli = os.path.join(GOLDEN, "sample_host.cofr"), os.path.join(GOLDEN, "sample_client.cofr")
        rc, out = self.run_cli("print", host, "--type", "digest", "--schema", sch)
        self.assertIn("mapstate", out)
        rc, out = self.run_cli("print", host, "--type", "digest")
        self.assertIn("story", out)
        rc, out = self.run_cli("diverge", os.path.join(GOLDEN, "desync_host.cofr"), os.path.join(GOLDEN, "desync_client.cofr"), "--schema", sch, "--check")
        self.assertEqual(rc, 1)
        self.assertIn("mapstate", out)
        rc, out = self.run_cli("diverge", host, cli, "--check")
        self.assertEqual(rc, 0)
        self.assertIn("No divergence", out)


# ---------------------------------------------------------------- C++ write, Python read

def write_python_trace(path):
    """The file the C++ test 'reads_the_trace_written_by_python' parses."""
    sch = S.Schema({"game": "from-python"})
    h = {"slot": 3, "role": 1, "reason": 2, "proto_version": 5, "wall_unix_ms": 1700000000000, "dump_t_us": 9, "session": 8, "epoch": 2}
    recs = [
        {"type": C.T_META, "mono_us": 0, "frame": 0, "meta": {"label": "py"}},
        {"type": C.T_SCHEMA, "mono_us": 0, "frame": 0, "schema": sch},
        {"type": C.T_NET_IN, "mono_us": 10, "frame": 1, "peer": 2, "channel": 0xFF, "msg_type": 4, "decode": 0, "session": 8, "epoch": 2,
         "seq": 5, "seq_hi": 6, "raw": b"\x01\x02\x03"},
        {"type": C.T_TXN_APPLIED, "mono_us": 11, "frame": 1, "seq": 5, "epoch": 2, "origin": 0, "index": 1, "applied_flags": 4, "hash": (1 << 64) - 1},
        {"type": C.T_DIGEST, "mono_us": 12, "frame": 1, "category": 0, "epoch": 2, "seq": 5, "hash": 3, "item_count": 1, "shards": [7, 8],
         "keys": {1 << 63: 5}, "bucketed": True},
        {"type": C.T_MARKER, "mono_us": 13, "frame": 1, "kind": 4, "text": "written by python"},
    ]
    C.dump(path, h, recs, sch)


class CrossTests(unittest.TestCase):
    """The C++ recorder writes, the Python reader reads."""

    def setUp(self):
        global CROSS
        CROSS = os.environ.get("COFR_CROSS_DIR")
        if not CROSS or not os.path.isdir(CROSS):
            self.skipTest("needs the files the C++ tests write (run without --no-cpp)")

    def test_fresh_sample_traces_equal_the_checked_in_golden_files(self):
        for n in ("sample_host.cofr", "sample_client.cofr", "desync_host.cofr", "desync_client.cofr"):
            self.assertEqual(read_bytes(os.path.join(CROSS, "fresh_" + n)), read_bytes(os.path.join(GOLDEN, n)), n)

    def test_everything_trace_field_by_field(self):
        data = read_bytes(os.path.join(CROSS, "everything.cofr"))
        tr = C.loads(data, "everything")
        self.assertEqual(tr["warnings"], [])
        h = tr["header"]
        self.assertEqual((h["slot"], h["role_name"], h["reason_name"], h["proto_version"], h["session"], h["epoch"], h["wall_unix_ms"]),
                         (2, "client", "desync", 7, 9, 4, 1700000000123))
        self.assertEqual(h["record_count"], len(tr["records"]))
        self.assertEqual(tr["meta"], {"label": "everything", "build": "x", "peer.0": "0"})
        self.assertEqual(tr["schema"].game, "toy")
        by = {}
        for r in tr["records"]:
            by.setdefault(r["name"], []).append(r)
        self.assertEqual([r["name"] for r in tr["records"][:2]], ["Meta", "Schema"])
        out = by["NetOut"][0]
        self.assertEqual((out["peer"], out["channel"], out["mux"], out["decode"], out["raw_len"], len(out["raw"]), out["truncated"], out["frame"]),
                         (3, 1, 0xD1, C.DECODE_FAILED, 5000, 1000, True, 3))
        self.assertEqual(out["mono_us"], 100)
        batch, dmsg = by["NetIn"]
        self.assertEqual((batch["peer"], batch["msg_type"], batch["decode"], batch["session"], batch["epoch"], batch["seq"], batch["seq_hi"], batch["frame"]),
                         (0, 4, C.DECODED, 4, 2, 7, 9, 4))
        self.assertEqual(batch["mono_us"], 200)
        self.assertEqual(dmsg["seq"], 77)
        derived = [r for r in by["Digest"] if r["derived"]]
        self.assertEqual(len(derived), 1)
        self.assertEqual((derived[0]["category"], derived[0]["epoch"], derived[0]["seq"], len(derived[0]["shards"]), derived[0]["shards"][5]), (0, 2, 77, 128, 0xDEAD))
        cap = by["TxnCaptured"][0]
        self.assertEqual((cap["kind"], cap["intent_id"], cap["seq"], cap["effect_count"], cap["hash"], cap["cause"], cap["epoch"]),
                         (1, 5, 0, 2, 0xAABBCCDDEEFF0011, 3, 4))
        ap = by["TxnApplied"][0]
        self.assertEqual((ap["seq"], ap["epoch"], ap["origin"], ap["index"], ap["applied_flags"], ap["cause"], ap["effect_tag"], ap["hash"]),
                         (12, 4, 1, 2, 2 | 8, 3, 12, 0x1122334455667788))
        self.assertEqual(tr["schema"].flag_names(ap["applied_flags"]), ["repair", "catch-up"])
        own = by["Ownership"][0]
        self.assertEqual((own["op"], own["actor"], own["epoch"], own["from_slot"], own["to_slot"], own["reason"], own["txn_id"]),
                         (1, 0xABCDEF0123, 7, 0, 2, 2, 99))
        plain = [r for r in by["Digest"] if not r["derived"] and not r["detail"] and not r["bucketed"]][0]
        self.assertEqual((plain["category"], plain["seq"], plain["hash"], plain["shards"], plain["keys"]),
                         (1, 12, 0x1122334455667788, [1, 2, 3], {10: 100, 11: 101}))
        main = [r for r in by["Digest"] if r["bucketed"] and not r["detail"] and not r["derived"]][0]
        details = [r for r in by["Digest"] if r["detail"]]
        self.assertEqual(len(details), 2)                                      # 5000 entries split over two records
        entries = {}
        for r in details:
            entries.update(r["keys"])
        self.assertEqual((len(entries), main["item_count"]), (5000, 5000))
        shards, h64 = C.bucketed_digest(entries.items())                        # the Python digest equals the C++ one
        self.assertEqual((shards, h64), (main["shards"], main["hash"]))
        self.assertTrue(any(r["text"].startswith("entry %016x " % next(iter(entries))) for r in by["Marker"]))
        sw = by["ScriptWrite"][0]
        self.assertEqual(sw["fields"], {"seq": 4, "key": "stage.q1", "value": -2})
        unk = by["Unknown99"][0]
        self.assertEqual(unk["payload"], b"\x09\x09")
        mk = [r for r in by["Marker"] if r["kind"] == 5][0]
        self.assertEqual(mk["text"], "saved é")
        self.assertEqual(tr["schema"].marker_kind(9), "checkpoint")
        self.assertEqual(C.dumps(tr["header"], C.to_records(tr), tr["schema"]), data)   # the Python writer reproduces the C++ bytes

    def test_python_writer_output_is_what_the_cpp_reader_expects(self):
        # written by write_python_trace before the C++ phase; the C++ test parsed it. Here: the file is still a valid trace.
        tr = C.load(os.path.join(CROSS, "from_python.cofr"))
        self.assertEqual(tr["header"]["record_count"], 6)
        self.assertEqual(tr["schema"].game, "from-python")


# ---------------------------------------------------------------- mutation twin

MUTATIONS = [
    ("cofr", "        if len(data) - pos - RECORD_HEADER < plen:\n            break", "        if False:\n            break", "truncated tail not detected"),
    ("cofr", "rec[\"malformed\"] = True\n        elif rtype == T_SCHEMA:", "rec[\"malformed\"] = False\n        elif rtype == T_SCHEMA:", "malformed bodies hidden"),
    ("cofr", "if h[\"version\"] != VERSION:", "if False:", "version not checked"),
    ("cofr", "if len(data) < 4 or data[:4] != MAGIC:", "if False:", "magic not checked"),
    ("cofr", "r[\"bucketed\"] = bool(r[\"flags\"] & FLAG_BUCKETED)", "r[\"bucketed\"] = False", "bucketed flag ignored"),
    ("cofr", "return _splitmix((key ^ _splitmix(value_hash)) & M64) & 0xFFFFFFFF", "return _splitmix((key ^ _splitmix(value_hash)) & M64) & 0x7FFFFFFF", "bucket mix differs from the C++ one"),
    ("cofr", "h = ((h ^ b) * 1099511628211) & M64", "h = ((h * 1099511628211) ^ b) & M64", "hash differs from the C++ one"),
    ("cofr", "rec[\"fields\"] = S.decode_custom(spec, rec[\"payload\"])", "rec[\"fields\"] = {}", "game-defined records not decoded"),
    ("cofr", "sch = schema or file_schema or S.default()", "sch = file_schema or S.default()", "external schema ignored"),
    ("cofr", "sch = schema or file_schema or S.default()", "sch = S.default()", "schema in the file ignored"),
    ("schema", "self.restate_mask = mask", "self.restate_mask = 7", "restate mask ignored"),
    ("schema", "self.ownership_owner_ops = set(_int_list(\"ownership_owner_ops\", merged[\"ownership_owner_ops\"]))", "self.ownership_owner_ops = {0, 1}", "owner ops ignored"),
    ("schema", "return self.txn_messages is None or n in self.txn_messages", "return True", "transaction message list ignored"),
    ("schema", "merged.update(data)", "pass", "schema keys do not replace the default"),
    ("schema", "if not FIRST_CUSTOM <= t <= 255:", "if False:", "custom type range not checked"),
    ("schema", "if f[\"name\"] in seen:", "if False:", "duplicate field names accepted"),
    ("schema", "if f[\"type\"] == \"bytes\" and i != len(clean) - 1:", "if False:", "bytes field in the middle accepted"),
    ("analyze", "a.offset_us[s] = int((fwd - back) / 2)", "a.offset_us[s] = int(fwd - back)", "clock offset wrong"),
    ("analyze", "c.sort(key=lambda x: (x[\"aligned_us\"], _PRIO[x[\"kind\"]], x[\"key\"]))", "c.sort(key=lambda x: (-x[\"aligned_us\"], _PRIO[x[\"kind\"]], x[\"key\"]))", "latest instead of earliest"),
    ("analyze", "if len(set(vals.values())) <= 1 and not diff_keys", "if len(set(vals.values())) < 0 and not diff_keys", "agreeing digests flagged"),
    ("analyze", "if len(lst) > 1:", "if len(lst) > 2:", "double apply missed"),
    ("analyze", "return not r[\"applied_flags\"] & a.schema.restate_mask", "return True", "repair restatements counted as divergence"),
    ("analyze", "owner_ops = a.schema.ownership_owner_ops", "owner_ops = {0, 1}", "ownership ops not taken from the schema"),
    ("analyze", "if len(owners) > 1:", "if len(owners) > 2:", "owner conflict missed"),
    ("analyze", "r[\"epoch\"] < prev", "r[\"epoch\"] <= prev", "idempotent regrant flagged"),
    ("analyze", "if gap or late:", "if gap:", "late txn missed"),
    ("analyze", "if gap or late:", "if late:", "gap txn missed"),
    ("analyze", "            if key[1] in a.traces:\n                a.lost.append", "            if False:\n                a.lost.append", "lost messages not found"),
    ("analyze", "known[int(k[5:])] = int(v)", "pass", "transport peer ids not mapped"),
    ("analyze", "if (s, head) in seen:", "if False:", "repeated markers not folded"),
    ("analyze", "r[\"type\"] == C.T_MARKER and not r.get(\"malformed\") and r[\"kind\"] == C.MARKER_DESYNC:", "r[\"type\"] == C.T_MARKER and not r.get(\"malformed\") and r[\"kind\"] == 0:", "desync markers ignored"),
    ("analyze", "t_lo = _last_agree(a, cand)\n        if t_lo is None:", "t_lo = None\n        if t_lo is None:", "window ignores last agreeing digest"),
    ("analyze", "elif r[\"peer_slot\"] in a.traces:\n            a.orphans.append", "elif False:\n            a.orphans.append", "orphans ignored"),
    ("analyze", "if k % nb in diff_shards]", "if True]", "cross-digest keys not limited to the differing buckets"),
    ("analyze", "\"bucket\": ki % nb if bucketed else None", "\"bucket\": ki & 0xFF if bucketed else None", "bucket count fixed at 256"),
    ("analyze", "bucketed = nb > 0 and any(r.get(\"bucketed\") for r in per.values())", "bucketed = nb > 0", "plain shards treated as key buckets"),
    ("analyze", "or d[\"captured\"]:", ":", "host commit counted as a missing apply"),
    ("analyze", "\"texts\": {s: a.entries.get(s, {}).get(ki) for s in slots}", "\"texts\": {s: None for s in slots}", "value text dropped"),
    ("analyze", "and a.schema.is_txn_message(r[\"msg_type\"])):", "and True):", "chain ignores the schema's transaction messages"),
    ("analyze", "elif r.get(\"custom\") and \"fields\" in r and", "elif False and", "game-defined records never direct"),
    ("analyze", "or r.get(\"custom\")):", "):", "game-defined records not in the chain"),
    ("shrink", "return r.get(\"diverged\") and signature(r) == sig", "return r.get(\"diverged\")", "different failure accepted"),
    ("shrink", "pinned = [i for i, s in enumerate(steps) if s.get(\"pin\")]", "pinned = []", "pinned steps removed"),
    ("shrink", "if line.startswith(\"VIOLATION \"):", "if False:", "violation lines ignored"),
    ("shrink", "if comp and len(comp) < len(cur) and test(comp):", "if False:", "complements never tried"),
    ("shrink", "if r[\"truncated\"] or not r[\"raw\"]:", "if False:", "truncated datagrams replayed"),
    ("shrink", "if p.returncode not in (0, 1):", "if p.returncode not in (0, 1, 2):", "bad fixture treated as converged"),
    ("shrink", "if runs[0] >= max_runs or", "if False or", "budget ignored"),
    ("shrink", "if count and test([]):", "if False:", "empty failing set not found"),
    ("shrink", "if not isinstance(result, dict) or \"diverged\" not in result:", "if False:", "bad hook result accepted"),
    ("shrink", "raise OracleError(\"the replay function raised %s: %s\" % (type(e).__name__, e))", "return {\"diverged\": False}", "hook crash treated as converged"),
    ("shrink", "if list_key:\n        if list_key not in fixture:", "if False:\n        if list_key not in fixture:", "named list ignored"),
    ("gentest", "\"converges\": True", "\"converges\": False", "wrong expectation emitted"),
    ("gentest", "re.sub(r\"[^a-z0-9_]+\", \"_\", s.lower())", "s.lower()", "unsafe file names"),
    ("report", "if nw and (nw[\"buckets\"] or nw[\"keys\"]):", "if False:", "narrowing missing from the report"),
    ("report", "(k[\"texts\"].get(s) or", "(\"\" or", "value text missing from the report"),
    ("report", "e(hd[\"instance\"])", "hd[\"instance\"]", "report not escaped"),
    ("report", "e(_step_text(st))", "_step_text(st)", "steps not escaped"),
    ("regress", "ok = got == want", "ok = got", "expected-divergence fixtures fail"),
    ("flight", "d = analyze.find_divergence(al)\n        if a.json:", "d = None\n        if a.json:", "diverge never finds anything"),
    ("flight", "return 1 if (a.check and d) else 0", "return 0", "diverge --check always succeeds"),
]
TWIN_MODS = ["cofr", "schema", "analyze", "shrink", "gentest", "report", "regress", "flight", "toy_replay"]


def _one_mutation(i, mod, old, new, why):
    d = tempfile.mkdtemp(prefix="cofr_mut%d_" % i)
    try:
        for m in TWIN_MODS:
            shutil.copy(os.path.join(HERE, m + ".py"), d)
        p = os.path.join(d, mod + ".py")
        with open(p, encoding="utf-8") as f:
            text = f.read()
        if text.count(old) != 1:
            return "TWIN BROKEN: %s: %s matches %d times" % (mod, why, text.count(old)), False
        with open(p, "w", encoding="utf-8") as f:
            f.write(text.replace(old, new))
        env = dict(os.environ, COFR_SRC=d)
        for extra in (["--quick"], []):      # the fast tests catch most mutants; the slow ones (replay programs, CLI) run only for the rest
            r = subprocess.run([sys.executable, "-I", os.path.join(HERE, "run_tests.py"), "--no-cpp", "--no-twin", "--fail-fast"] + extra,
                               capture_output=True, text=True, env=env, errors="replace")
            if r.returncode != 0:
                break
        if r.returncode == 0:
            return "SURVIVED: %s: %s" % (mod, why), False
        return "caught  : %s: %s" % (mod, why), True
    finally:
        shutil.rmtree(d, ignore_errors=True)


def twin():
    from concurrent.futures import ThreadPoolExecutor
    survived = []
    with ThreadPoolExecutor(max_workers=4) as ex:
        for msg, ok in ex.map(lambda t: _one_mutation(*t), [(i,) + m for i, m in enumerate(MUTATIONS)]):
            print(msg)
            if not ok:
                survived.append(msg)
    return survived


# ---------------------------------------------------------------- C++ phase

def cpp_phase(cross_dir):
    """Configure and build the recorder and its tests with cmake (Visual Studio 2022 on Windows, one compile at a time),
    run every ctest case (unit, golden, perf and the mutation twins), then run the golden group once more with
    COFR_EMIT_DIR so it leaves the files the cross tests read. Returns (ok, summary)."""
    cmake, ctest = shutil.which("cmake"), shutil.which("ctest")
    if not cmake or not ctest:
        return False, "cmake and ctest are needed for the C++ tests (use --no-cpp to skip them)"
    build = os.environ.get("COFR_BUILD_DIR") or os.path.join(tempfile.gettempdir(), "cofr-flight-build")
    env = dict(os.environ)
    env.pop("CMAKE_TOOLCHAIN_FILE", None)       # a cross-compile toolchain set for another project would break the host build
    os.makedirs(build, exist_ok=True)
    cache = os.path.join(build, "CMakeCache.txt")
    if not os.path.exists(cache):
        gens = [["-G", "Visual Studio 17 2022", "-A", "x64"], ["-DCMAKE_BUILD_TYPE=Release"]] if os.name == "nt" else [["-DCMAKE_BUILD_TYPE=Release"]]
        for g in gens:
            r = subprocess.run([cmake, "-S", CPP_DIR, "-B", build] + g, capture_output=True, text=True, env=env, errors="replace")
            if r.returncode == 0:
                break
            shutil.rmtree(build, ignore_errors=True)
            os.makedirs(build, exist_ok=True)
        else:
            return False, "cmake configure failed:\n" + (r.stdout + r.stderr)[-1500:]
    vs = "Visual Studio" in read_text(cache)
    cmd = [cmake, "--build", build, "--config", "Release", "--parallel", "1"]
    if vs:
        cmd += ["--", "/nologo", "/v:minimal", "/p:IgnoreWarnIntDirInTempDetected=true"]
    r = subprocess.run(cmd, capture_output=True, text=True, env=env, errors="replace")
    if r.returncode != 0:
        return False, "C++ build failed:\n" + (r.stdout + r.stderr)[-3000:]
    t = subprocess.run([ctest, "--test-dir", build, "-C", "Release", "--output-on-failure"], capture_output=True, text=True, env=env, errors="replace")
    tail = [ln for ln in t.stdout.splitlines() if "tests passed" in ln or "tests failed" in ln]
    if t.returncode != 0:
        return False, "C++ tests failed:\n" + t.stdout[-3000:]
    exe = [p for p in glob.glob(os.path.join(build, "**", "cofr_tests*"), recursive=True) if os.path.isfile(p) and p.endswith(("cofr_tests", "cofr_tests.exe"))]
    if not exe:
        return False, "cofr_tests was not built"
    e2 = dict(env, COFR_EMIT_DIR=cross_dir, COFR_GOLDEN_DIR=GOLDEN)
    r = subprocess.run([exe[0], "--group", "golden"], capture_output=True, text=True, env=e2, errors="replace")
    if r.returncode != 0:
        return False, "the C++ cross test files could not be written:\n" + r.stdout[-2000:]
    listing = subprocess.run([exe[0], "--list"], capture_output=True, text=True, env=env, errors="replace").stdout.split()
    n_twin = sum(1 for x in listing if x.startswith("twin."))
    return True, "C++: %s (%d tests in cofr_tests, %d of them mutation twins)" % (tail[0].strip() if tail else "ctest ok", len(listing), n_twin)


def read_text(path):
    try:
        with open(path, encoding="utf-8", errors="replace") as f:
            return f.read()
    except OSError:
        return ""


# ---------------------------------------------------------------- main

def main():
    argv = sys.argv[1:]
    quick, no_cpp, no_twin = "--quick" in argv, "--no-cpp" in argv or "--quick" in argv, "--no-twin" in argv or "--quick" in argv
    cross = None
    try:
        if not no_cpp:
            cross = tempfile.mkdtemp(prefix="cofr_cross_")
            write_python_trace(os.path.join(cross, "from_python.cofr"))
            ok, msg = cpp_phase(cross)
            print(msg)
            if not ok:
                print("TESTS FAILED")
                return 1
            os.environ["COFR_CROSS_DIR"] = cross     # the cross tests, and the twin's child runs, read it
        suite = unittest.defaultTestLoader.loadTestsFromModule(sys.modules[__name__])
        res = unittest.TextTestRunner(verbosity=1, failfast="--fail-fast" in argv).run(suite)
        if not res.wasSuccessful():
            print("TESTS FAILED")
            return 1
        skipped = len(res.skipped)
        print("Python: %d tests run%s" % (res.testsRun, ", %d skipped" % skipped if skipped else ""))
        if quick:
            print("QUICK OK (fast Python tests only; run without --quick for ALL OK)")
            return 0
        if no_twin:
            print("TESTS OK (the mutation twin did not run, so this is not ALL OK)")
            return 0
        survived = twin()
        if survived:
            print("%d mutation(s) survived" % len(survived))
            return 1
        print("%d Python mutations, all caught" % len(MUTATIONS))
        if no_cpp:
            print("PYTHON OK (the C++ phase did not run, so this is not ALL OK)")
            return 0
        print("ALL OK")
        return 0
    finally:
        if cross:
            shutil.rmtree(cross, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
