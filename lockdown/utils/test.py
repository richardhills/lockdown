from unittest.case import TestCase
from lockdown.utils.utils import WeakIdentityKeyDictionary
import gc


class Key(object):
    pass


class TestWeakIdentityKeyDictionary(TestCase):
    def test_init_empty(self):
        foo = WeakIdentityKeyDictionary()
        self.assertEqual(len(foo), 0)

    def test_init_with_single_data(self):
        key = Key()
        foo = WeakIdentityKeyDictionary({ key: 10 })
        self.assertEqual(len(foo), 1)
        self.assertEqual(foo[key], 10)

    def test_init_with_multi_data(self):
        key1 = Key()
        key2 = Key()
        key3 = Key()
        key4 = Key()

        foo = WeakIdentityKeyDictionary({ key1: 10, key2: 4, key3: 123, key4: 31 })
        self.assertEqual(len(foo), 4)
        self.assertEqual(foo[key1], 10)
        self.assertEqual(foo[key2], 4)
        self.assertEqual(foo[key3], 123)
        self.assertEqual(foo[key4], 31)

    def test_setter(self):
        key1 = Key()

        foo = WeakIdentityKeyDictionary()
        foo[key1] = 4
        self.assertEqual(len(foo), 1)
        self.assertEqual(foo[key1], 4)

    def test_setter2(self):
        key1 = Key()

        foo = WeakIdentityKeyDictionary()
        foo[key1] = 4
        foo[key1] = 6
        foo[key1] = 9
        self.assertEqual(len(foo), 1)
        self.assertEqual(foo[key1], 9)

    def test_deleter(self):
        key1 = Key()

        foo = WeakIdentityKeyDictionary()
        foo[key1] = 4
        del foo[key1]

        self.assertEqual(len(foo), 0)
        with self.assertRaises(KeyError):
            foo[key1]

    def test_basic_gc(self):
        key1 = Key()

        foo = WeakIdentityKeyDictionary()
        foo[key1] = 4

        key1 = None

        self.assertEqual(len(foo), 0)

    def test_multi_basic_gc(self):
        key1 = Key()
        key2 = Key()
        key3 = Key()
        key4 = Key()

        foo = WeakIdentityKeyDictionary()
        foo[key1] = 4
        foo[key2] = 8
        foo[key3] = 12
        foo[key4] = 16

        key1 = None
        self.assertEqual(len(foo), 3)
        key2 = None
        self.assertEqual(len(foo), 2)
        key3 = None
        self.assertEqual(len(foo), 1)
        key4 = None
        self.assertEqual(len(foo), 0)

    def test_gc_and_recreate(self):
        foo = WeakIdentityKeyDictionary()

        key = Key()
        foo[key] = 4
        key = None
        key = Key()
        foo[key] = 6
        key = None
        key = Key()
        foo[key] = 8
        key = None
        key = Key()
        foo[key] = 10
        key = None

        self.assertEqual(len(foo), 0)

    def test_circular_keys(self):
        key1 = Key()
        key2 = Key()

        key1.a = key2
        key2.a = key1

        foo = WeakIdentityKeyDictionary()
        foo[key1] = 5
        foo[key2] = 8

        self.assertEqual(foo[key1], 5)
        self.assertEqual(foo[key2], 8)

        key1 = None

        self.assertEqual(len(foo), 2)
        gc.collect()
        self.assertEqual(len(foo), 2)

        key2 = None

        self.assertEqual(len(foo), 2)
        gc.collect()
        self.assertEqual(len(foo), 0)
