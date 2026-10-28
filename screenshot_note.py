#!/usr/bin/python3
"""Ubuntu 기본 스크린샷에 빨간 선을 그리는 작은 상주 도구."""

import argparse
import gettext
from pathlib import Path
import signal
import sys

import gi
gi.require_version('Gtk', '3.0')
gi.require_version('Gdk', '3.0')
gi.require_version('GdkPixbuf', '2.0')
from gi.repository import Gdk, GdkPixbuf, Gio, GLib, Gtk
from PIL import Image, ImageDraw


def pixbuf(image):
    image = image.convert('RGB')
    return GdkPixbuf.Pixbuf.new_from_bytes(
        GLib.Bytes.new(image.tobytes()), GdkPixbuf.Colorspace.RGB,
        False, 8, image.width, image.height, image.width * 3,
    )


class Drawing:
    def __init__(self, image):
        self.original = image.convert('RGB')
        self.strokes = []

    def undo(self):
        if self.strokes:
            self.strokes.pop()

    def render(self, size=None):
        size = size or self.original.size
        result = self.original.resize(size, Image.Resampling.LANCZOS)
        draw = ImageDraw.Draw(result)
        sx, sy = size[0] / self.original.width, size[1] / self.original.height
        width = max(1, round(5 * min(sx, sy)))
        radius = width / 2
        for stroke in self.strokes:
            points = [(x * sx, y * sy) for x, y in stroke]
            if not points:
                continue
            if len(points) > 1:
                draw.line(points, fill='#ff0000', width=width, joint='curve')
            for x, y in (points[0], points[-1]):
                draw.ellipse((x-radius, y-radius, x+radius, y+radius), fill='#ff0000')
        return result


class Editor(Gtk.ApplicationWindow):
    def __init__(self, app, image):
        super().__init__(application=app, title='스크린샷 메모')
        self.drawing = Drawing(image)
        self.dragging = False
        self.redraw_id = 0
        self.set_resizable(False)
        self.set_position(Gtk.WindowPosition.CENTER)

        display = Gdk.Display.get_default()
        monitor = display.get_primary_monitor() or display.get_monitor(0)
        area = monitor.get_workarea()
        scale = min(1, max(1, area.width - 100) / image.width,
                    max(1, area.height - 180) / image.height)
        self.preview_size = (max(1, int(image.width * scale)),
                             max(1, int(image.height * scale)))

        column = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8)
        column.set_border_width(10)
        self.add(column)
        toolbar = Gtk.Box(spacing=12)
        toolbar.pack_start(Gtk.Label(label='빨간 펜 · Esc: 선 취소'), True, True, 0)
        copy_button = Gtk.Button(label='복사 후 닫기  Ctrl+C')
        copy_button.connect('clicked', self.copy_and_close)
        toolbar.pack_end(copy_button, False, False, 0)
        column.pack_start(toolbar, False, False, 0)

        self.picture = Gtk.Image()
        canvas = Gtk.EventBox()
        canvas.set_halign(Gtk.Align.CENTER)
        canvas.set_valign(Gtk.Align.CENTER)
        canvas.add(self.picture)
        canvas.add_events(Gdk.EventMask.BUTTON_PRESS_MASK |
                          Gdk.EventMask.BUTTON_RELEASE_MASK |
                          Gdk.EventMask.POINTER_MOTION_MASK)
        canvas.connect('button-press-event', self.press)
        canvas.connect('motion-notify-event', self.motion)
        canvas.connect('button-release-event', self.release)
        canvas.connect('realize', lambda widget: widget.get_window().set_cursor(
            Gdk.Cursor.new_from_name(display, 'crosshair')))
        column.pack_start(canvas, True, True, 0)
        self.connect('key-press-event', self.keypress)
        self.connect('destroy', self.cleanup)
        self.refresh()
        self.show_all()
        self.present()

    def point(self, event):
        width, height = self.drawing.original.size
        return (min(width-1, max(0, event.x * width / self.preview_size[0])),
                min(height-1, max(0, event.y * height / self.preview_size[1])))

    def press(self, _widget, event):
        if event.button != 1:
            return False
        self.dragging = True
        self.drawing.strokes.append([self.point(event)])
        self.queue_refresh()
        return True

    def motion(self, _widget, event):
        if self.dragging:
            self.drawing.strokes[-1].append(self.point(event))
            self.queue_refresh()
        return True

    def release(self, _widget, event):
        if event.button == 1 and self.dragging:
            self.drawing.strokes[-1].append(self.point(event))
            self.dragging = False
            self.queue_refresh()
        return True

    def queue_refresh(self):
        if not self.redraw_id:
            self.redraw_id = GLib.timeout_add(16, self.refresh)

    def refresh(self):
        self.redraw_id = 0
        self.picture.set_from_pixbuf(pixbuf(self.drawing.render(self.preview_size)))
        return GLib.SOURCE_REMOVE

    def keypress(self, _widget, event):
        if event.keyval == Gdk.KEY_Escape:
            self.dragging = False
            self.drawing.undo()
            self.queue_refresh()
            return True
        if event.state & Gdk.ModifierType.CONTROL_MASK and event.keyval in (Gdk.KEY_c, Gdk.KEY_C):
            self.copy_and_close()
            return True
        return False

    def copy_and_close(self, *_args):
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_image(pixbuf(self.drawing.render()))
        clipboard.set_can_store(None)
        # The application stays alive after this window closes and owns the image.
        clipboard.store()
        self.destroy()

    def cleanup(self, *_args):
        if self.redraw_id:
            GLib.source_remove(self.redraw_id)
            self.redraw_id = 0


class ScreenshotWatcher:
    """Only newly created PNG files; wait for writes and coalesce file events."""
    def __init__(self, directory, on_image):
        self.directory = Path(directory)
        self.on_image = on_image
        self.pending = {}
        self.seen = set(self.directory.glob('*.png'))
        self.monitor = Gio.File.new_for_path(str(self.directory)).monitor_directory(
            Gio.FileMonitorFlags.WATCH_MOVES, None)
        self.monitor.connect('changed', self.changed)

    def changed(self, _monitor, file, other, event):
        if event == Gio.FileMonitorEvent.RENAMED and other:
            file = other
        path = Path(file.get_path())
        if path.suffix.lower() != '.png' or path in self.seen or path in self.pending:
            return
        if event in (Gio.FileMonitorEvent.DELETED, Gio.FileMonitorEvent.MOVED_OUT):
            return
        state = {'tries': 0, 'stat': None}
        self.pending[path] = GLib.timeout_add(200, self.load_ready, path, state)

    def load_ready(self, path, state):
        state['tries'] += 1
        try:
            stat = path.stat()
            signature = (stat.st_size, stat.st_mtime_ns)
            if state['stat'] != signature:
                state['stat'] = signature
                if state['tries'] < 30:
                    return GLib.SOURCE_CONTINUE
                raise OSError('파일 저장이 끝나지 않았습니다')
            with Image.open(path) as source:
                source.load()
                image = source.convert('RGB')
        except (OSError, ValueError) as exc:
            if state['tries'] < 30:
                return GLib.SOURCE_CONTINUE
            print(f'스크린샷을 열지 못했습니다: {path}: {exc}', file=sys.stderr)
        else:
            self.seen.add(path)
            self.on_image(image)
        self.pending.pop(path, None)
        return GLib.SOURCE_REMOVE

    def close(self):
        self.monitor.cancel()
        for source_id in self.pending.values():
            GLib.source_remove(source_id)
        self.pending.clear()


def screenshot_directory():
    pictures = GLib.get_user_special_dir(GLib.UserDirectory.DIRECTORY_PICTURES)
    return Path(pictures or GLib.get_home_dir()) / gettext.dgettext('gnome-shell', 'Screenshots')


class ScreenshotApp(Gtk.Application):
    def __init__(self):
        super().__init__(application_id='local.personal.ScreenshotNote',
                         flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.watcher = None

    def do_startup(self):
        Gtk.Application.do_startup(self)
        self.hold()
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, self.stop)
        GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGINT, self.stop)

    def stop(self):
        self.quit()
        return GLib.SOURCE_REMOVE

    def do_command_line(self, command):
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument('--quit', action='store_true', help='상주 도구 종료')
        parser.add_argument('--image', type=Path, help='특정 이미지로 편집 창 열기')
        parser.add_argument('--watch-dir', type=Path, help='감시할 스크린샷 폴더')
        try:
            args = parser.parse_args(command.get_arguments()[1:])
        except SystemExit as exc:
            if not self.watcher:
                self.quit()
            return exc.code
        if args.quit:
            self.quit()
            return 0
        try:
            if not self.watcher:
                directory = (args.watch_dir or screenshot_directory()).resolve()
                directory.mkdir(parents=True, exist_ok=True)
                self.watcher = ScreenshotWatcher(directory, lambda image: Editor(self, image))
                print(f'캡처 대기 중: {directory}', flush=True)
            if args.image:
                with Image.open(args.image) as image:
                    image.load()
                    Editor(self, image)
        except (OSError, GLib.Error) as exc:
            command.printerr(f'실행할 수 없습니다: {exc}\n')
            if not self.watcher:
                self.quit()
            return 1
        return 0

    def do_shutdown(self):
        if self.watcher:
            self.watcher.close()
        Gtk.Application.do_shutdown(self)


if __name__ == '__main__':
    raise SystemExit(ScreenshotApp().run(sys.argv))
