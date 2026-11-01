import sys
import unittest
from pathlib import Path

sys.path.insert(0,str(Path(__file__).resolve().parents[1] / 'tools'))
from ssb_patch_fixed import patched_bytes,sha256

class PatchTest(unittest.TestCase):
    def sample(self):
        b = bytearray(b'\x02\x00\x00\x00'*8)
        old='食の悩みです。▼'.encode('utf8')
        b.extend(old+b'\0')
        while len(b)%4:b.append(0)
        row={'id':'ssb_00000020','offset_hex':'0x20','original_bytes':str(len(old)),
             'source_ja':'食の悩みです。▼','translation_ru':'С едой.▼'}
        return bytes(b),row

    def test_one_replacement_keeps_bounds_and_terminal(self):
        orig,row=self.sample()
        out,changes=patched_bytes(orig,[row],expected_sha=sha256(orig))
        self.assertEqual(len(orig),len(out))
        self.assertEqual(orig[:32],out[:32])
        self.assertEqual(out[32:32+len('С едой.▼'.encode('utf8'))].decode('utf8'),'С едой.▼')
        self.assertEqual(out[32+len('С едой.▼'.encode('utf8')):],bytes(len(orig)-32-len('С едой.▼'.encode('utf8'))))
        self.assertEqual(len(changes),1)

    def test_round_trip_no_changes(self):
        orig,row=self.sample();row['translation_ru']=''
        output,patches=patched_bytes(orig,[row]);self.assertEqual(orig,output);self.assertEqual(patches,[])

    def test_reject_missing_marker(self):
        orig,row=self.sample();row['translation_ru']='Привет'
        with self.assertRaises(ValueError):patched_bytes(orig,[row])

    def test_reject_overlong(self):
        orig,row=self.sample();row['translation_ru']='Очень длинная длинная длинная реплика.▼'
        with self.assertRaises(ValueError):patched_bytes(orig,[row])

    def test_reject_wrong_source(self):
        orig,row=self.sample();row['source_ja']='Привет!▼'
        with self.assertRaises(ValueError):patched_bytes(orig,[row])

    def test_reject_changed_baseline(self):
        orig,row=self.sample()
        with self.assertRaises(ValueError):patched_bytes(orig,[row],expected_sha='0'*64)

if __name__=='__main__':unittest.main()
