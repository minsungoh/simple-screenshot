import tempfile
import time
import unittest
from pathlib import Path
from types import SimpleNamespace

from screenshot_note import Drawing, Editor, ScreenshotWatcher, Gdk, GLib, Gtk, Image


def drain_until(predicate, timeout=3):
    deadline = time.monotonic() + timeout
    context = GLib.MainContext.default()
    while time.monotonic() < deadline:
        while context.pending():
            context.iteration(False)
        if predicate():
            return True
        time.sleep(0.01)
    return False


class DrawingTest(unittest.TestCase):
    def test_undo_restores_exact_original_and_export_size(self):
        original = Image.new('RGB', (1600, 900), 'white')
        drawing = Drawing(original)
        drawing.strokes.append([(50, 50), (100, 50)])
        drawing.strokes.append([(300, 300)])
        self.assertEqual(drawing.render().getpixel((75, 50)), (255, 0, 0))
        self.assertEqual(drawing.render().getpixel((300, 300)), (255, 0, 0))
        self.assertEqual(drawing.render((800, 450)).size, (800, 450))
        self.assertEqual(drawing.render().size, original.size)
        drawing.undo()
        self.assertEqual(drawing.render().getpixel((300, 300)), (255, 255, 255))
        drawing.undo()
        drawing.undo()
        self.assertEqual(drawing.render().tobytes(), original.tobytes())


class WatcherTest(unittest.TestCase):
    def test_existing_files_ignored_partial_write_retried_and_events_deduplicated(self):
        with tempfile.TemporaryDirectory() as directory:
            old = Path(directory) / 'old.png'
            Image.new('RGB', (10, 10)).save(old)
            received = []
            watcher = ScreenshotWatcher(directory, received.append)
            try:
                path = Path(directory) / 'new.png'
                path.write_bytes(b'\x89PNG')
                drain_until(lambda: False, 0.5)
                self.assertEqual(received, [])
                Image.new('RGB', (30, 20), 'white').save(path)
                self.assertTrue(drain_until(lambda: len(received) == 1))
                self.assertEqual(received[0].size, (30, 20))
                path.touch()
                drain_until(lambda: False, 0.5)
                self.assertEqual(len(received), 1)
                temporary = Path(directory) / 'atomic.tmp'
                Image.new('RGB', (50, 40)).save(temporary, format='PNG')
                temporary.rename(Path(directory) / 'atomic.png')
                self.assertTrue(drain_until(lambda: len(received) == 2))
                self.assertEqual(received[1].size, (50, 40))
            finally:
                watcher.close()


@unittest.skipUnless(Gdk.Display.get_default(), '화면 연결 필요')
class EditorTest(unittest.TestCase):
    def setUp(self):
        self.app = Gtk.Application(application_id=None)
        self.app.register(None)
        self.window = Editor(self.app, Image.new('RGB', (1600, 900), 'white'))

    def tearDown(self):
        self.window.destroy()

    def test_esc_undo_copy_and_window_close(self):
        self.window.press(None, SimpleNamespace(button=1, x=50, y=50))
        self.window.motion(None, SimpleNamespace(x=100, y=50))
        self.window.release(None, SimpleNamespace(button=1, x=150, y=50))
        self.window.keypress(None, SimpleNamespace(keyval=Gdk.KEY_Escape, state=0))
        self.assertEqual(self.window.drawing.strokes, [])
        self.assertTrue(self.window.get_visible())
        self.window.press(None, SimpleNamespace(button=1, x=50, y=50))
        self.window.release(None, SimpleNamespace(button=1, x=100, y=50))
        point = self.window.drawing.strokes[0][0]
        self.window.keypress(None, SimpleNamespace(
            keyval=Gdk.KEY_c, state=Gdk.ModifierType.CONTROL_MASK))
        self.assertFalse(self.window.get_visible())
        copied = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD).wait_for_image()
        self.assertIsNotNone(copied)
        self.assertEqual((copied.get_width(), copied.get_height()), (1600, 900))
        offset = round(point[1]) * copied.get_rowstride() + round(point[0]) * copied.get_n_channels()
        self.assertEqual(bytes(copied.get_pixels()[offset:offset+3]), b'\xff\x00\x00')


if __name__ == '__main__':
    unittest.main()
