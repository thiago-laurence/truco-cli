import asyncio
import unittest

from truco.wire import read_message, write_message


class WireTests(unittest.IsolatedAsyncioTestCase):
    async def test_reads_and_writes_newline_terminated_json_objects(self):
        reader = asyncio.StreamReader()
        reader.feed_data(b'{"type":"chat","text":"hola"}\n')
        reader.feed_eof()
        self.assertEqual(await read_message(reader), {"type": "chat", "text": "hola"})

        class Writer:
            def __init__(self):
                self.data = None

            def write(self, data):
                self.data = data

            async def drain(self):
                pass

        writer = Writer()
        await write_message(writer, {"type": "chat", "text": "hola"})
        self.assertEqual(writer.data, b'{"type": "chat", "text": "hola"}\n')

    async def test_rejects_json_that_is_not_an_object(self):
        reader = asyncio.StreamReader()
        reader.feed_data(b'[]\n')
        reader.feed_eof()
        with self.assertRaises((ValueError, UnicodeError)):
            await read_message(reader)

    async def test_rejects_malformed_json(self):
        reader = asyncio.StreamReader()
        reader.feed_data(b'{"type":]\n')
        reader.feed_eof()
        with self.assertRaises(ValueError):
            await read_message(reader)

    async def test_rejects_non_finite_json_constants(self):
        for data in (b'{"x":NaN}\n', b'{"x":Infinity}\n'):
            with self.subTest(data=data):
                reader = asyncio.StreamReader()
                reader.feed_data(data)
                reader.feed_eof()
                with self.assertRaises(ValueError):
                    await read_message(reader)

    async def test_refuses_to_write_non_finite_numbers(self):
        class Writer:
            def write(self, data):
                self.data = data

            async def drain(self):
                pass

        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                writer = Writer()
                with self.assertRaises(ValueError):
                    await write_message(writer, {"x": value})
                self.assertFalse(hasattr(writer, "data"))

    async def test_rejects_messages_over_4096_bytes(self):
        reader = asyncio.StreamReader()
        reader.feed_data(b'{"text":"' + b"x" * 4090 + b'"}\n')
        reader.feed_eof()
        with self.assertRaises((ValueError, asyncio.LimitOverrunError)):
            await read_message(reader)


if __name__ == "__main__":
    unittest.main()
