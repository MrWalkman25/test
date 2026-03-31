from gi.repository import Gdk, Gtk


APP_CSS = """
/* Modern CSS for Task Manager - Corrected for GTK4 */

@define-color accent_blue #3584e4;
@define-color accent_red #e01b24;
@define-color accent_green #2ec27e;
@define-color accent_purple #c061cb;

.section {
    border-radius: 24px;
    padding: 16px;
    background: alpha(@window_fg_color, 0.05);
    border: 1px solid alpha(@window_fg_color, 0.03);
    transition: all 400ms ease;
}

.panel-title {
    font-size: 1.1em;
    font-weight: 800;
    margin-bottom: 8px;
    letter-spacing: -0.02em;
}

/* Task List Item Styling */
.task-row {
    margin-bottom: 8px;
    border-radius: 18px;
    padding: 12px;
    background: alpha(@window_fg_color, 0.04);
    border: 1px solid alpha(@window_fg_color, 0.02);
    transition: transform 150ms ease, background 200ms ease, box-shadow 300ms ease;
}

.task-row:hover {
    background: alpha(@window_fg_color, 0.08);
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.1);
}

.task-row-overdue {
    background: alpha(@accent_red, 0.08); /* Re-subtle for premium look */
    border: 1px solid alpha(@accent_red, 0.3);
    border-left: 5px solid @accent_red; /* Strong left accent */
}

.task-row-overdue:hover {
    background: alpha(@accent_red, 0.12);
}

.task-title {
    font-weight: 700;
    font-size: 1.05em;
    color: @window_fg_color;
}

.task-meta {
    opacity: 0.6;
    font-size: 0.85em;
}

/* Chips / Status Tags */
.calendar-chip {
    border-radius: 10px;
    padding: 4px 10px;
    font-size: 11px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    transition: all 200ms ease;
}

/* Compact mode chips padding */
.calendar-day-box .calendar-chip {
    padding: 2px 6px;
    font-size: 10px;
}

.calendar-chip:hover {
    filter: brightness(1.1);
    transform: translateY(-1px);
}

.quick-action-bar {
    opacity: 0.2;
    transition: opacity 200ms ease;
    margin-left: 8px;
}

.task-row:hover .quick-action-bar,
.calendar-chip:hover .quick-action-bar {
    opacity: 1.0;
}

.quick-action-btn {
    padding: 0;
    min-width: 28px;
    min-height: 28px;
    border-radius: 6px;
    color: alpha(@window_fg_color, 0.6);
}

.quick-action-btn:hover {
    background: alpha(@window_fg_color, 0.1);
    color: @window_fg_color;
}

.quick-action-btn-done:hover {
    color: @accent_green;
}

.quick-action-btn-delete:hover {
    color: @accent_red;
}

.chip-overdue {
    background: @accent_red;
    color: white;
    box-shadow: 0 2px 6px alpha(@accent_red, 0.3);
}

.chip-muted {
    background: alpha(@window_fg_color, 0.12);
    color: alpha(@window_fg_color, 0.8);
}

.chip-active {
    background: alpha(@accent_blue, 0.15);
    color: @accent_blue;
}

.chip-new {
    background: alpha(@accent_green, 0.15);
    color: #26a269;
}

/* Calendar Overdue Indicator */
.day-overdue-indicator {
    color: @accent_red;
    font-size: 10px;
    font-weight: 900;
    margin-left: 2px;
}

.calendar-day-box-overdue {
    border: 1px solid alpha(@accent_red, 0.2);
}

/* Calendar Day Box */
.calendar-day-box {
    border-radius: 18px;
    padding: 10px;
    margin: 4px;
    background: alpha(@window_fg_color, 0.03);
    border: 1px solid transparent;
    transition: background 250ms ease, border-color 250ms ease;
}

.calendar-day-box:hover {
    background: alpha(@accent_blue, 0.08);
    border-color: alpha(@accent_blue, 0.15);
}

.calendar-day-title {
    font-weight: 800;
    font-size: 1.2em;
    opacity: 0.9;
    margin-bottom: 4px;
}

/* Header & Switcher Refinement */
headerbar {
    background: transparent;
    border-bottom: 1px solid alpha(@window_fg_color, 0.05);
}

stackswitcher {
    padding: 6px;
    background: alpha(@window_fg_color, 0.06);
    border-radius: 16px;
}

stackswitcher button {
    border-radius: 12px;
    padding: 6px 16px;
    font-weight: 700;
    margin: 0 4px;
}

/* Popover Styling - Fixing the "box in a box" look */
popover > contents {
    padding: 0;
    border-radius: 24px;
    background: @window_bg_color;
    box-shadow: 0 10px 40px rgba(0, 0, 0, 0.25);
    border: 1px solid alpha(@window_fg_color, 0.1);
}

.popover-card {
    padding: 18px;
    background: transparent;
    border-radius: 24px;
}

.overdue-text {
    color: @accent_red;
    font-weight: 700;
}
.overdue-section {
    background: alpha(@accent_red, 0.05);
    border-radius: 24px;
    padding: 12px;
    border: 1px solid alpha(@accent_red, 0.1);
}

.overdue-section .panel-title {
    color: @accent_red;
}

.transparent-list {
    background: transparent;
}
"""


def setup_css() -> None:
    provider = Gtk.CssProvider()
    provider.load_from_data(APP_CSS.encode("utf-8"))
    Gtk.StyleContext.add_provider_for_display(
        Gdk.Display.get_default(),
        provider,
        Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
    )
