#!/usr/bin/env python3
"""
Claude Approval LED — Floating indicator + stats overlay panel.
"""

import os
import socket
import threading

import objc
from AppKit import (
    NSApplication,
    NSWindow,
    NSWindowStyleMaskBorderless,
    NSBackingStoreBuffered,
    NSFloatingWindowLevel,
    NSColor,
    NSView,
    NSBezierPath,
    NSApp,
    NSApplicationActivationPolicyAccessory,
    NSScreen,
    NSFont,
    NSFontAttributeName,
    NSForegroundColorAttributeName,
    NSAttributedString,
    NSTrackingArea,
    NSTrackingMouseEnteredAndExited,
    NSTrackingActiveAlways,
    NSParagraphStyleAttributeName,
    NSParagraphStyle,
)
from Foundation import NSMakeRect, NSObject, NSMakePoint, NSTimer
from Quartz import (
    CGWindowListCopyWindowInfo,
    kCGWindowListOptionOnScreenOnly,
    kCGNullWindowID,
    kCGWindowListExcludeDesktopElements,
)

import stats

SOCKET_PATH = "/tmp/claude-approval-led.sock"
BANNER_HEIGHT = 28
DOT_SIZE = 14
STATS_PANEL_W = 260
STATS_PANEL_H = 280

TERMINAL_APPS = ("Warp", "Code", "Cursor", "stable", "Terminal", "iTerm2")


def find_warp_window():
    windows = CGWindowListCopyWindowInfo(
        kCGWindowListOptionOnScreenOnly | kCGWindowListExcludeDesktopElements,
        kCGNullWindowID,
    )
    if not windows:
        return None
    for w in windows:
        owner = w.get("kCGWindowOwnerName", "")
        if any(name in owner for name in TERMINAL_APPS):
            b = w.get("kCGWindowBounds")
            layer = w.get("kCGWindowLayer", 0)
            if b and layer == 0:
                return {"x": b["X"], "y": b["Y"], "w": b["Width"], "h": b["Height"]}
    return None


def make_dot_window(x, y):
    """Small floating dot indicator."""
    size = DOT_SIZE + 8
    win = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(x, y, size, size),
        NSWindowStyleMaskBorderless, NSBackingStoreBuffered, False,
    )
    win.setLevel_(NSFloatingWindowLevel + 100)
    win.setOpaque_(False)
    win.setBackgroundColor_(NSColor.clearColor())
    win.setIgnoresMouseEvents_(False)
    win.setCollectionBehavior_(1 << 0 | 1 << 4)
    win.setHasShadow_(False)
    view = DotView.alloc().initWithFrame_(NSMakeRect(0, 0, size, size))
    win.setContentView_(view)
    win.orderFrontRegardless()
    return win


def make_banner_window(x, y, w):
    """Red alert banner."""
    win = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(x, y, w, BANNER_HEIGHT),
        NSWindowStyleMaskBorderless, NSBackingStoreBuffered, False,
    )
    win.setLevel_(NSFloatingWindowLevel + 100)
    win.setOpaque_(False)
    win.setBackgroundColor_(NSColor.clearColor())
    win.setIgnoresMouseEvents_(True)
    win.setCollectionBehavior_(1 << 0 | 1 << 4)
    win.setHasShadow_(True)
    view = BannerView.alloc().initWithFrame_(NSMakeRect(0, 0, w, BANNER_HEIGHT))
    win.setContentView_(view)
    return win


def make_stats_window(x, y):
    """Stats overlay panel."""
    win = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        NSMakeRect(x, y, STATS_PANEL_W, STATS_PANEL_H),
        NSWindowStyleMaskBorderless, NSBackingStoreBuffered, False,
    )
    win.setLevel_(NSFloatingWindowLevel + 101)
    win.setOpaque_(False)
    win.setBackgroundColor_(NSColor.clearColor())
    win.setIgnoresMouseEvents_(True)
    win.setCollectionBehavior_(1 << 0 | 1 << 4)
    win.setHasShadow_(True)
    view = StatsView.alloc().initWithFrame_(NSMakeRect(0, 0, STATS_PANEL_W, STATS_PANEL_H))
    win.setContentView_(view)
    return win


def run_socket_server(delegate):
    if os.path.exists(SOCKET_PATH):
        os.unlink(SOCKET_PATH)
    srv = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    srv.bind(SOCKET_PATH)
    srv.listen(5)

    while True:
        conn = None
        try:
            conn, _ = srv.accept()
            data = conn.recv(512).decode().strip()
            conn.close()
            conn = None

            if not data:
                continue

            parts = data.split(" ", 1)
            cmd = parts[0].lower()
            arg = parts[1].strip() if len(parts) > 1 else ""

            if cmd == "show":
                delegate.performSelectorOnMainThread_withObject_waitUntilDone_(
                    "doShow:", arg, False
                )
            elif cmd == "hide":
                delegate.performSelectorOnMainThread_withObject_waitUntilDone_(
                    "doHide:", None, False
                )
            elif cmd == "push":
                delegate.performSelectorOnMainThread_withObject_waitUntilDone_(
                    "doPush:", None, False
                )
            elif cmd == "stats":
                delegate.performSelectorOnMainThread_withObject_waitUntilDone_(
                    "doToggleStats:", None, False
                )
            elif cmd == "quit":
                delegate.performSelectorOnMainThread_withObject_waitUntilDone_(
                    "doQuit:", None, False
                )
                break
        except Exception as e:
            print(f"Socket error: {e}", flush=True)
            if conn:
                try:
                    conn.close()
                except Exception:
                    pass


class DotView(NSView):
    """The small green/red dot that floats on screen. Hover to show stats."""

    def initWithFrame_(self, frame):
        self = objc.super(DotView, self).initWithFrame_(frame)
        if self is None:
            return None
        self._alert = False
        self._delegate = None
        return self

    def updateTrackingAreas(self):
        objc.super(DotView, self).updateTrackingAreas()
        for ta in self.trackingAreas():
            self.removeTrackingArea_(ta)
        ta = NSTrackingArea.alloc().initWithRect_options_owner_userInfo_(
            self.bounds(),
            NSTrackingMouseEnteredAndExited | NSTrackingActiveAlways,
            self,
            None,
        )
        self.addTrackingArea_(ta)

    def mouseEntered_(self, event):
        if self._delegate:
            self._delegate.showStats()

    def mouseExited_(self, event):
        if self._delegate:
            self._delegate.scheduleHideStats()

    def drawRect_(self, rect):
        w = self.bounds().size.width
        h = self.bounds().size.height

        NSColor.clearColor().set()
        NSBezierPath.fillRect_(rect)

        dot_x = (w - DOT_SIZE) / 2
        dot_y = (h - DOT_SIZE) / 2

        if self._alert:
            NSColor.colorWithCalibratedRed_green_blue_alpha_(1.0, 0.15, 0.15, 1.0).set()
        else:
            NSColor.colorWithCalibratedRed_green_blue_alpha_(0.15, 0.9, 0.15, 1.0).set()

        NSBezierPath.bezierPathWithOvalInRect_(
            NSMakeRect(dot_x, dot_y, DOT_SIZE, DOT_SIZE)
        ).fill()

    def setAlert_(self, v):
        self._alert = v
        self.setNeedsDisplay_(True)


class BannerView(NSView):
    """Red approval-needed banner."""

    def initWithFrame_(self, frame):
        self = objc.super(BannerView, self).initWithFrame_(frame)
        if self is None:
            return None
        self._tab_name = ""
        return self

    def drawRect_(self, rect):
        w = self.bounds().size.width
        h = self.bounds().size.height

        NSColor.colorWithCalibratedRed_green_blue_alpha_(0.6, 0.05, 0.05, 0.95).set()
        path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            NSMakeRect(0, 0, w, h), 6, 6
        )
        path.fill()

        NSColor.colorWithCalibratedRed_green_blue_alpha_(1.0, 0.2, 0.2, 0.6).set()
        path.setLineWidth_(1.5)
        path.stroke()

        dot_x = 10
        dot_y = (h - 10) / 2
        NSColor.colorWithCalibratedRed_green_blue_alpha_(1.0, 0.15, 0.15, 1.0).set()
        NSBezierPath.bezierPathWithOvalInRect_(
            NSMakeRect(dot_x, dot_y, 10, 10)
        ).fill()

        text = f"  Approval needed: {self._tab_name}" if self._tab_name else "  Approval needed"
        attrs = {
            NSFontAttributeName: NSFont.boldSystemFontOfSize_(12),
            NSForegroundColorAttributeName: NSColor.colorWithCalibratedRed_green_blue_alpha_(
                1.0, 0.9, 0.9, 1.0
            ),
        }
        s = NSAttributedString.alloc().initWithString_attributes_(text, attrs)
        s.drawAtPoint_(NSMakePoint(dot_x + 10 + 6, (h - s.size().height) / 2))

    def setTabName_(self, name):
        self._tab_name = name
        self.setNeedsDisplay_(True)


class StatsView(NSView):
    """Floating stats panel showing today's stats, streak, and history."""

    def initWithFrame_(self, frame):
        self = objc.super(StatsView, self).initWithFrame_(frame)
        if self is None:
            return None
        return self

    def drawRect_(self, rect):
        w = self.bounds().size.width
        h = self.bounds().size.height

        # Background
        NSColor.colorWithCalibratedRed_green_blue_alpha_(0.08, 0.08, 0.08, 0.95).set()
        path = NSBezierPath.bezierPathWithRoundedRect_xRadius_yRadius_(
            NSMakeRect(0, 0, w, h), 10, 10
        )
        path.fill()

        # Border
        NSColor.colorWithCalibratedRed_green_blue_alpha_(0.3, 0.3, 0.3, 0.6).set()
        path.setLineWidth_(1.0)
        path.stroke()

        # Get stats
        today = stats.get_today()
        streak = stats.get_streak()
        history = stats.get_history(7)

        y_pos = h - 8  # Start from top with padding

        # Title
        y_pos -= 22
        draw_text(self,"Claude LED", 16, True, 15, y_pos, w,
                        0.15, 0.9, 0.15)

        # Divider
        y_pos -= 10
        NSColor.colorWithCalibratedRed_green_blue_alpha_(0.3, 0.3, 0.3, 0.5).set()
        NSBezierPath.fillRect_(NSMakeRect(15, y_pos, w - 30, 1))

        # Today section
        y_pos -= 22
        draw_text(self,"TODAY", 10, True, 15, y_pos, w,
                        0.5, 0.5, 0.5)

        y_pos -= 22
        draw_text(self,f"Approvals:  {today['approvals']}", 13, False, 20, y_pos, w,
                        1.0, 1.0, 1.0)

        y_pos -= 20
        draw_text(self,f"Pushes:  {today['pushes']}", 13, False, 20, y_pos, w,
                        1.0, 1.0, 1.0)

        y_pos -= 24
        streak_text = f"Streak:  {streak} day{'s' if streak != 1 else ''}"
        draw_text(self,streak_text, 13, True, 20, y_pos, w,
                        1.0, 0.8, 0.2)

        # Divider
        y_pos -= 10
        NSColor.colorWithCalibratedRed_green_blue_alpha_(0.3, 0.3, 0.3, 0.5).set()
        NSBezierPath.fillRect_(NSMakeRect(15, y_pos, w - 30, 1))

        # History
        y_pos -= 20
        draw_text(self,"LAST 7 DAYS", 10, True, 15, y_pos, w,
                        0.5, 0.5, 0.5)

        for day in history:
            y_pos -= 18
            if y_pos < 10:
                break
            date_short = day["date"][5:]  # MM-DD
            label = f"{date_short}    {day['approvals']}A   {day['pushes']}P"
            draw_text(self,label, 11, False, 20, y_pos, w,
                            0.7, 0.7, 0.7)

def draw_text(view, text, size, bold, x, y, max_w, r, g, b):
    font = NSFont.boldSystemFontOfSize_(size) if bold else NSFont.systemFontOfSize_(size)
    attrs = {
        NSFontAttributeName: font,
        NSForegroundColorAttributeName: NSColor.colorWithCalibratedRed_green_blue_alpha_(
            r, g, b, 1.0
        ),
    }
    s = NSAttributedString.alloc().initWithString_attributes_(text, attrs)
    s.drawAtPoint_(NSMakePoint(x, y))


class AppDelegate(NSObject):
    def init(self):
        self = objc.super(AppDelegate, self).init()
        self.dotWindow = None
        self.dotView = None
        self.bannerWindow = None
        self.bannerView = None
        self.statsWindow = None
        self.statsView = None
        self.screenHeight = 0.0
        self.statsVisible = False
        self.hideStatsTimer = None
        self.alertTimer = None
        return self

    def applicationDidFinishLaunching_(self, notification):
        self.screenHeight = NSScreen.mainScreen().frame().size.height

        warp = find_warp_window()
        if warp:
            # Place dot at top-right of terminal window
            dot_size = DOT_SIZE + 8
            dx = float(warp["x"]) + float(warp["w"]) - dot_size - 15
            dy_cg = float(warp["y"]) + 45
            dy = self.screenHeight - dy_cg - dot_size
        else:
            dot_size = DOT_SIZE + 8
            dx = NSScreen.mainScreen().frame().size.width - dot_size - 30
            dy = self.screenHeight - 80

        # Create dot
        self.dotWindow = make_dot_window(dx, dy)
        self.dotView = self.dotWindow.contentView()
        self.dotView._delegate = self
        self.dotView.setAlert_(False)

        # Create banner (hidden initially)
        self.bannerWindow = make_banner_window(0, 0, 300)
        self.bannerView = self.bannerWindow.contentView()

        # Create stats panel (hidden initially)
        stats_x = dx - STATS_PANEL_W + dot_size
        stats_y = dy - STATS_PANEL_H - 5
        self.statsWindow = make_stats_window(stats_x, stats_y)

        t = threading.Thread(target=run_socket_server, args=(self,), daemon=True)
        t.start()
        print(f"Claude LED running. Socket: {SOCKET_PATH}", flush=True)

    def showStats(self):
        if self.hideStatsTimer:
            self.hideStatsTimer.invalidate()
            self.hideStatsTimer = None
        self.statsView = self.statsWindow.contentView()
        self.statsView.setNeedsDisplay_(True)
        self.statsWindow.orderFrontRegardless()
        self.statsVisible = True

    def scheduleHideStats(self):
        if self.hideStatsTimer:
            self.hideStatsTimer.invalidate()
        self.hideStatsTimer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
            0.5, self, "hideStatsTimer:", None, False
        )

    def hideStatsTimer_(self, timer):
        self.statsWindow.orderOut_(None)
        self.statsVisible = False
        self.hideStatsTimer = None

    def positionBannerOnWarp_(self, bw):
        warp = find_warp_window()
        if not warp:
            return
        cx = float(warp["x"]) + (float(warp["w"]) - bw) / 2
        cy = float(warp["y"]) + 65
        ny = self.screenHeight - cy - BANNER_HEIGHT
        self.bannerWindow.setFrame_display_(
            NSMakeRect(cx, ny, bw, BANNER_HEIGHT), True
        )

    def doShow_(self, arg):
        try:
            # Cancel any pending auto-hide
            if self.alertTimer:
                self.alertTimer.invalidate()
                self.alertTimer = None

            tab_name = str(arg) if arg else ""
            text_w = len(tab_name) * 8 if tab_name else 0
            bw = max(250, 200 + text_w)
            warp = find_warp_window()
            if warp:
                bw = min(bw, int(warp["w"]) - 20)
            self.positionBannerOnWarp_(bw)
            self.bannerView.setTabName_(tab_name)
            self.bannerWindow.orderFrontRegardless()
            self.dotView.setAlert_(True)
            count = stats.increment_approvals()
            if self.statsVisible:
                self.statsView.setNeedsDisplay_(True)

            # Auto-hide after 30 seconds
            self.alertTimer = NSTimer.scheduledTimerWithTimeInterval_target_selector_userInfo_repeats_(
                30.0, self, "autoHideAlert:", None, False
            )
            print(f"ALERT: '{tab_name}' (approvals today: {count})", flush=True)
        except Exception as e:
            print(f"doShow error: {e}", flush=True)

    def autoHideAlert_(self, timer):
        self.doHide_(None)
        self.alertTimer = None

    def doHide_(self, sender):
        try:
            self.bannerWindow.orderOut_(None)
            self.dotView.setAlert_(False)
            if self.statsVisible:
                self.statsView.setNeedsDisplay_(True)
            print("IDLE (green)", flush=True)
        except Exception as e:
            print(f"doHide error: {e}", flush=True)

    def doPush_(self, sender):
        try:
            count = stats.increment_pushes()
            if self.statsVisible:
                self.statsView.setNeedsDisplay_(True)
            print(f"PUSH recorded (pushes today: {count})", flush=True)
        except Exception as e:
            print(f"doPush error: {e}", flush=True)

    def doToggleStats_(self, sender):
        if self.statsVisible:
            self.statsWindow.orderOut_(None)
            self.statsVisible = False
        else:
            self.showStats()

    def doQuit_(self, sender):
        NSApp.terminate_(None)


def main():
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyAccessory)
    delegate = AppDelegate.alloc().init()
    app.setDelegate_(delegate)
    app.run()


if __name__ == "__main__":
    main()
