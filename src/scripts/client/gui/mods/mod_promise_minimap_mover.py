# -*- coding: utf-8 -*-
"""
Promise Minimap Mover 1.1.2

Controls:
    Ctrl + click on minimap
        Normal World of Tanks minimap action (ping, etc.).

    Ctrl + Shift + LMB + drag
        Move the minimap. A 5 px threshold separates a click from a drag.

Config (position + size):
    <preferences>/mods/promise/minimap_mover.cfg
    Format: offset_x offset_y size_index
"""
from __future__ import print_function

import logging
import math
import os

import BigWorld
import Keys

from gui import InputHandler
from helpers import getPreferencesDirPath
from gui.Scaleform.daapi.view.battle.shared.minimap.component import (
    MinimapComponent
)


# ===========================================================================
# Mod information
# ===========================================================================

__version__ = '1.1.2'
MOD_VERSION = __version__
MOD_NAME = 'MinimapMover'

_LOGGER = logging.getLogger('Promise.MinimapMover')


def log(message):
    _LOGGER.info('[%s %s] %s', MOD_NAME, MOD_VERSION, message)


# ===========================================================================
# Constants
# ===========================================================================

POLL_INTERVAL = 0.02
DRAG_THRESHOLD = 5.0
REFRESH_DELAY = 0.05


# ===========================================================================
# State
# ===========================================================================

_minimap = None

_offset_x = 0.0
_offset_y = 0.0
_base_x = None
_base_y = None
_base_locked = False

_saved_size = None      # from cfg
_battle_size = None     # frozen once per battle before any as_setSize

_poll_callback = None
_refresh_callback = None
_apply_callbacks = []

_mouse_was_down = False
_drag_candidate = False
_dragging = False
_drag_start_x = None
_drag_start_y = None
_last_x = None
_last_y = None

_installed = False
_original_populate = None
_original_dispose = None


# ===========================================================================
# Configuration
# ===========================================================================

def _get_config_directory():
    try:
        base = getPreferencesDirPath()
        if not base:
            _LOGGER.error('getPreferencesDirPath() returned empty path')
            return None
        return os.path.join(base, 'mods', 'promise')
    except Exception:
        _LOGGER.exception('Unable to determine preferences directory')
    return None


def _get_config_path():
    folder = _get_config_directory()
    if folder is None:
        return None
    return os.path.join(folder, 'minimap_mover.cfg')


def _is_finite(value):
    try:
        return not (math.isnan(value) or math.isinf(value))
    except Exception:
        return False


def load_offset():
    global _offset_x, _offset_y, _saved_size
    _offset_x = 0.0
    _offset_y = 0.0
    _saved_size = None

    path = _get_config_path()
    if not path:
        return
    if not os.path.isfile(path):
        log('No saved position yet')
        return

    try:
        f = open(path, 'r')
        try:
            data = f.read().strip()
        finally:
            f.close()

        parts = data.replace(',', ' ').split()
        if len(parts) < 2:
            log('Invalid config; using default position')
            return

        ox = float(parts[0])
        oy = float(parts[1])
        if not _is_finite(ox) or not _is_finite(oy):
            log('Non-finite offset; using default position')
            return

        _offset_x = ox
        _offset_y = oy

        if len(parts) >= 3:
            try:
                sz = int(float(parts[2]))
                if 0 <= sz <= 5:
                    _saved_size = sz
            except Exception:
                pass

        log(
            'Loaded offset %.1f %.1f size=%s'
            % (_offset_x, _offset_y, _saved_size)
        )
    except Exception:
        _offset_x = 0.0
        _offset_y = 0.0
        _saved_size = None
        _LOGGER.exception('Unable to load saved minimap position')


def save_offset():
    path = _get_config_path()
    if not path:
        return

    size = _battle_size
    if size is None:
        size = _saved_size
    if size is None:
        size = read_minimap_size_from_settings()

    folder = os.path.dirname(path)
    try:
        if not os.path.isdir(folder):
            os.makedirs(folder)

        temporary = path + '.tmp'
        f = open(temporary, 'w')
        try:
            f.write(
                '%.2f %.2f %d\n'
                % (_offset_x, _offset_y, int(size))
            )
        finally:
            f.close()

        if os.path.isfile(path):
            os.remove(path)
        os.rename(temporary, path)
        log(
            'Saved offset %.1f %.1f size=%s'
            % (_offset_x, _offset_y, size)
        )
    except Exception:
        _LOGGER.exception('Unable to save minimap position')


# ===========================================================================
# Input helpers
# ===========================================================================

def _key_down(key):
    try:
        return BigWorld.isKeyDown(key)
    except Exception:
        return False


def ctrl_down():
    return _key_down(Keys.KEY_LCONTROL) or _key_down(Keys.KEY_RCONTROL)


def shift_down():
    return _key_down(Keys.KEY_LSHIFT) or _key_down(Keys.KEY_RSHIFT)


def modifiers_active():
    return ctrl_down() and shift_down()


def is_lmb_held():
    for name in ('KEY_LEFTMOUSE', 'KEY_MOUSE0', 'KEY_MOUSELEFT'):
        key = getattr(Keys, name, None)
        if key is None:
            continue
        try:
            if BigWorld.isKeyDown(key):
                return True
        except Exception:
            pass
    return False


# ===========================================================================
# Screen / mouse
# ===========================================================================

def get_screen_size():
    try:
        return BigWorld.screenSize()
    except Exception:
        pass
    try:
        import GUI
        return GUI.screenResolution()
    except Exception:
        pass
    return 1920, 1080


def get_mouse_pos():
    try:
        pos = BigWorld.getCursorPos()
        if pos is not None:
            return float(pos[0]), float(pos[1])
    except Exception:
        pass
    try:
        import GUI
        pos = GUI.mcursor().position
        x = float(pos[0])
        y = float(pos[1])
        sw, sh = get_screen_size()
        if -1.5 <= x <= 1.5 and -1.5 <= y <= 1.5:
            x = (x + 1.0) * 0.5 * sw
            y = (1.0 - y) * 0.5 * sh
        return x, y
    except Exception:
        pass
    return None


# ===========================================================================
# Minimap access
# ===========================================================================

def get_flash():
    if _minimap is None:
        return None
    try:
        return _minimap.flashObject
    except Exception:
        return None


def get_display_info():
    flash = get_flash()
    if flash is None:
        return None
    try:
        return flash.getDisplayInfo()
    except Exception:
        return None


def get_minimap_size_pixels():
    if _minimap is not None:
        try:
            size = _minimap._getMinimapSize()
            if size is not None and len(size) >= 2:
                w, h = float(size[0]), float(size[1])
                if w > 0.0 and h > 0.0:
                    return w, h
        except Exception:
            pass

    info = get_display_info()
    if info is not None:
        try:
            w = float(info.width)
            h = float(info.height)
            if w > 0.0 and h > 0.0:
                return w, h
        except Exception:
            pass

    flash = get_flash()
    if flash is not None:
        try:
            w = float(flash.width)
            h = float(flash.height)
            if w > 0.0 and h > 0.0:
                return w, h
        except Exception:
            pass
    return None


def clamp_offset_to_screen():
    global _offset_x, _offset_y
    if not _base_locked or _base_x is None or _base_y is None:
        return

    sw, sh = get_screen_size()
    size = get_minimap_size_pixels()
    if size is None:
        w, h = 200.0, 200.0
    else:
        w, h = size

    target_x = _base_x + _offset_x
    target_y = _base_y + _offset_y

    min_x = -w * 0.75
    min_y = -h * 0.75
    max_x = sw - w * 0.25
    max_y = sh - h * 0.25

    clamped_x = max(min_x, min(max_x, target_x))
    clamped_y = max(min_y, min(max_y, target_y))

    _offset_x = clamped_x - _base_x
    _offset_y = clamped_y - _base_y


# ===========================================================================
# Position
# ===========================================================================

def apply_position(x, y):
    flash = get_flash()
    if flash is None:
        return False
    try:
        info = flash.getDisplayInfo()
        info.x = float(x)
        info.y = float(y)
        flash.setDisplayInfo(info)
        return True
    except Exception:
        _LOGGER.exception('Unable to move minimap')
    return False


def lock_base_from_layout():
    global _base_x, _base_y, _base_locked
    if _base_locked:
        return True
    info = get_display_info()
    if info is None:
        return False
    try:
        _base_x = float(info.x)
        _base_y = float(info.y)
        _base_locked = True
        log('Base position %.1f %.1f' % (_base_x, _base_y))
        return True
    except Exception:
        _LOGGER.exception('Unable to determine original minimap position')
    return False


def reapply_offset():
    if not _base_locked or _base_x is None or _base_y is None:
        return
    apply_position(_base_x + _offset_x, _base_y + _offset_y)


def move_minimap_by(dx, dy):
    global _offset_x, _offset_y
    if not _base_locked:
        if not lock_base_from_layout():
            return
    _offset_x += float(dx)
    _offset_y += float(dy)
    reapply_offset()


# ===========================================================================
# Size / refresh
# ===========================================================================

def read_minimap_size_from_settings():
    try:
        from account_helpers.settings_core.settings_constants import GAME
        from helpers import dependency
        from skeletons.account_helpers.settings_core import ISettingsCore

        settings_core = dependency.instance(ISettingsCore)
        value = settings_core.getSetting(GAME.MINIMAP_SIZE)
        if isinstance(value, (int, long)):
            return int(value)
    except Exception:
        _LOGGER.exception('Unable to read minimap size setting')
    return 2


def write_minimap_size_to_settings(index):
    try:
        from account_helpers.settings_core.settings_constants import GAME
        from helpers import dependency
        from skeletons.account_helpers.settings_core import ISettingsCore

        settings_core = dependency.instance(ISettingsCore)
        index = int(index)

        if hasattr(settings_core, 'applySetting'):
            settings_core.applySetting(GAME.MINIMAP_SIZE, index)
        elif hasattr(settings_core, 'setSetting'):
            settings_core.setSetting(GAME.MINIMAP_SIZE, index)

        for name in ('applyStorages', 'save', 'forceSave'):
            fn = getattr(settings_core, name, None)
            if not callable(fn):
                continue
            try:
                if name == 'applyStorages':
                    fn(False)
                else:
                    fn()
                break
            except Exception:
                pass
        return True
    except Exception:
        _LOGGER.exception('Unable to write minimap size setting')
    return False


def set_minimap_display_size(index):
    flash = get_flash()
    if flash is None:
        return False
    try:
        if hasattr(flash, 'as_setSize'):
            flash.as_setSize(int(index))
            return True
    except Exception:
        _LOGGER.exception('Unable to set minimap display size')
    return False


def freeze_battle_size():
    """
    Capture the size we will restore for this battle.
    Must run before any as_setSize, otherwise settings may already be wrong.
    """
    global _battle_size
    if _battle_size is not None:
        return _battle_size

    live = read_minimap_size_from_settings()

    # If settings are stuck at default 2 but cfg has another size, trust cfg.
    if _saved_size is not None and live == 2 and _saved_size != 2:
        _battle_size = int(_saved_size)
    else:
        _battle_size = int(live)

    log('Battle minimap size frozen to %s' % _battle_size)
    return _battle_size


def cancel_refresh():
    global _refresh_callback
    if _refresh_callback is None:
        return
    try:
        BigWorld.cancelCallback(_refresh_callback)
    except Exception:
        pass
    _refresh_callback = None


def refresh_minimap():
    """
    Nudge size once to clear the black hole, then restore the frozen size
    into both Flash and the settings plugin (two passes).
    """
    global _refresh_callback
    if _minimap is None:
        return

    cancel_refresh()

    preferred = freeze_battle_size()
    temporary = preferred - 1 if preferred > 0 else preferred + 1

    log(
        'Refreshing minimap %s -> %s -> %s'
        % (preferred, temporary, preferred)
    )

    set_minimap_display_size(temporary)
    reapply_offset()

    def restore_pass(pass_id):
        global _refresh_callback
        _refresh_callback = None
        if _minimap is None:
            return

        set_minimap_display_size(preferred)
        write_minimap_size_to_settings(preferred)
        reapply_offset()
        log('Minimap size restore pass %s -> %s' % (pass_id, preferred))

        if pass_id == 1:
            _refresh_callback = BigWorld.callback(
                0.08,
                lambda: restore_pass(2)
            )

    _refresh_callback = BigWorld.callback(
        REFRESH_DELAY,
        lambda: restore_pass(1)
    )


# ===========================================================================
# Callback management
# ===========================================================================

def cancel_poll():
    global _poll_callback
    if _poll_callback is None:
        return
    try:
        BigWorld.cancelCallback(_poll_callback)
    except Exception:
        pass
    _poll_callback = None


def cancel_apply_callbacks():
    global _apply_callbacks
    callbacks = list(_apply_callbacks)
    _apply_callbacks = []
    for callback_id in callbacks:
        try:
            BigWorld.cancelCallback(callback_id)
        except Exception:
            pass


def schedule_apply(delay, tag):
    holder = [None]

    def callback():
        callback_id = holder[0]
        try:
            if callback_id in _apply_callbacks:
                _apply_callbacks.remove(callback_id)
        except Exception:
            pass

        if _minimap is None:
            return
        if not lock_base_from_layout():
            return

        freeze_battle_size()
        clamp_offset_to_screen()
        reapply_offset()
        log(
            '[%s] position %.1f %.1f'
            % (tag, _base_x + _offset_x, _base_y + _offset_y)
        )

        if tag == 'initial' and (
            abs(_offset_x) > 0.5 or abs(_offset_y) > 0.5
        ):
            refresh_minimap()

    callback_id = BigWorld.callback(delay, callback)
    holder[0] = callback_id
    _apply_callbacks.append(callback_id)


# ===========================================================================
# Drag state
# ===========================================================================

def reset_drag_state():
    global _mouse_was_down, _drag_candidate, _dragging
    global _drag_start_x, _drag_start_y, _last_x, _last_y
    _mouse_was_down = False
    _drag_candidate = False
    _dragging = False
    _drag_start_x = None
    _drag_start_y = None
    _last_x = None
    _last_y = None


def begin_drag_candidate(mouse_x, mouse_y):
    global _drag_candidate, _drag_start_x, _drag_start_y, _last_x, _last_y

    # No hit-test: DisplayInfo and cursor space disagree on this client.
    # Ctrl+Shift is the gate; DRAG_THRESHOLD separates click from drag.
    _drag_candidate = True
    _drag_start_x = mouse_x
    _drag_start_y = mouse_y
    _last_x = mouse_x
    _last_y = mouse_y
    log('Drag candidate at %.0f %.0f' % (mouse_x, mouse_y))
    return True


def finish_drag():
    global _dragging, _drag_candidate
    global _drag_start_x, _drag_start_y, _last_x, _last_y

    was_dragging = _dragging
    _dragging = False
    _drag_candidate = False
    _drag_start_x = None
    _drag_start_y = None
    _last_x = None
    _last_y = None

    if not was_dragging:
        return

    clamp_offset_to_screen()
    reapply_offset()
    save_offset()
    refresh_minimap()
    log('Drag finished')


# ===========================================================================
# Mouse polling
# ===========================================================================

def start_poll():
    global _poll_callback
    if _poll_callback is not None:
        return
    _poll_callback = BigWorld.callback(POLL_INTERVAL, poll_mouse)


def poll_mouse():
    global _poll_callback, _mouse_was_down, _dragging, _last_x, _last_y

    _poll_callback = None

    if _minimap is None:
        return

    if not modifiers_active():
        if _dragging:
            finish_drag()
        else:
            reset_drag_state()
        return

    position = get_mouse_pos()
    if position is None:
        start_poll()
        return

    mouse_x, mouse_y = position
    mouse_down = is_lmb_held()

    if mouse_down and not _mouse_was_down:
        begin_drag_candidate(mouse_x, mouse_y)

    elif mouse_down and _mouse_was_down:
        if _drag_candidate:
            if not _dragging:
                dx = mouse_x - _drag_start_x
                dy = mouse_y - _drag_start_y
                if (dx * dx + dy * dy) >= (DRAG_THRESHOLD * DRAG_THRESHOLD):
                    _dragging = True
                    _last_x = mouse_x
                    _last_y = mouse_y
                    log('Drag started %.0f %.0f' % (mouse_x, mouse_y))
            else:
                dx = mouse_x - _last_x
                dy = mouse_y - _last_y
                if abs(dx) > 0.01 or abs(dy) > 0.01:
                    move_minimap_by(dx, dy)
                _last_x = mouse_x
                _last_y = mouse_y

    elif not mouse_down and _mouse_was_down:
        if _dragging:
            finish_drag()
        else:
            reset_drag_state()

    _mouse_was_down = mouse_down
    start_poll()


# ===========================================================================
# Keyboard
# ===========================================================================

def on_key_event(event):
    try:
        key = event.key
        if key not in (
            Keys.KEY_LCONTROL,
            Keys.KEY_RCONTROL,
            Keys.KEY_LSHIFT,
            Keys.KEY_RSHIFT
        ):
            return False

        if modifiers_active():
            start_poll()
        else:
            if _dragging:
                finish_drag()
            else:
                reset_drag_state()
            cancel_poll()
    except Exception:
        _LOGGER.exception('Keyboard handler failed')
    return False


# ===========================================================================
# Battle lifecycle
# ===========================================================================

def teardown_battle():
    global _minimap, _base_x, _base_y, _base_locked, _battle_size
    cancel_poll()
    cancel_refresh()
    cancel_apply_callbacks()
    reset_drag_state()
    _minimap = None
    _base_x = None
    _base_y = None
    _base_locked = False
    _battle_size = None


def _populate_wrapper(self):
    teardown_battle()
    _original_populate(self)
    try:
        global _minimap, _base_x, _base_y, _base_locked, _battle_size
        _minimap = self
        _base_x = None
        _base_y = None
        _base_locked = False
        _battle_size = None
        load_offset()
        log('Minimap registered')
        # Freeze size before any refresh can call as_setSize.
        BigWorld.callback(0.15, freeze_battle_size)
        schedule_apply(0.25, 'initial')
        schedule_apply(1.0, 'late')
    except Exception:
        _LOGGER.exception('Minimap populate hook failed')


def _dispose_wrapper(self):
    try:
        teardown_battle()
    except Exception:
        _LOGGER.exception('Battle cleanup failed')
    if _original_dispose is not None:
        return _original_dispose(self)


# ===========================================================================
# Install / uninstall
# ===========================================================================

def init():
    global _installed, _original_populate, _original_dispose
    if _installed:
        return
    try:
        _original_populate = MinimapComponent._populate
        MinimapComponent._populate = _populate_wrapper

        if hasattr(MinimapComponent, '_dispose'):
            _original_dispose = MinimapComponent._dispose
            MinimapComponent._dispose = _dispose_wrapper

        InputHandler.g_instance.onKeyDown += on_key_event
        InputHandler.g_instance.onKeyUp += on_key_event

        _installed = True
        log('Loaded')
    except Exception:
        _LOGGER.exception('Unable to install MinimapMover')


def fini():
    global _installed, _original_populate, _original_dispose
    if not _installed:
        return

    teardown_battle()

    try:
        InputHandler.g_instance.onKeyDown -= on_key_event
    except Exception:
        pass
    try:
        InputHandler.g_instance.onKeyUp -= on_key_event
    except Exception:
        pass

    try:
        if (
            _original_populate is not None and
            MinimapComponent._populate is _populate_wrapper
        ):
            MinimapComponent._populate = _original_populate
    except Exception:
        pass

    try:
        if (
            _original_dispose is not None and
            getattr(MinimapComponent, '_dispose', None) is _dispose_wrapper
        ):
            MinimapComponent._dispose = _original_dispose
    except Exception:
        pass

    _installed = False
    log('Unloaded')


init()