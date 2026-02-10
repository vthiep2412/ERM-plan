@echo off
setlocal EnableDelayedExpansion

set "COMMENT_LINE=# This line was added at the bottom to force re-check."

:: List of Python files to modify
set "FILES="
set "FILES=!FILES! C:\Users\vthie\.vscode\ERM-plan\verify_syntax.py"
set "FILES=!FILES! C:\Users\vthie\.vscode\ERM-plan\verify_cursor_syntax.py"
set "FILES=!FILES! C:\Users\vthie\.vscode\ERM-plan\test_volume.py"
set "FILES=!FILES! C:\Users\vthie\.vscode\ERM-plan\test_regex.py"
set "FILES=!FILES! C:\Users\vthie\.vscode\ERM-plan\run_pipreqs.py"
set "FILES=!FILES! C:\Users\vthie\.vscode\ERM-plan\check_nvenc.py"
set "FILES=!FILES! C:\Users\vthie\.vscode\ERM-plan\MyDesk\viewer\widgets.py"
set "FILES=!FILES! C:\Users\vthie\.vscode\ERM-plan\MyDesk\viewer\webrtc_client.py"
set "FILES=!FILES! C:\Users\vthie\.vscode\ERM-plan\MyDesk\viewer\webcam_window.py"
set "FILES=!FILES! C:\Users\vthie\.vscode\ERM-plan\MyDesk\viewer\troll_tab.py"
set "FILES=!FILES! C:\Users\vthie\.vscode\ERM-plan\MyDesk\viewer\shell_tab.py"
set "FILES=!FILES! C:\Users\vthie\.vscode\ERM-plan\MyDesk\viewer\settings_tab.py"
set "FILES=!FILES! C:\Users\vthie\.vscode\ERM-plan\MyDesk\viewer\session_worker.py"
set "FILES=!FILES! C:\Users\vthie\.vscode\ERM-plan\MyDesk\viewer\session.py"
set "FILES=!FILES! C:\Users\vthie\.vscode\ERM-plan\MyDesk\viewer\pm_tab.py"
set "FILES=!FILES! C:\Users\vthie\.vscode\ERM-plan\MyDesk\viewer\main.py"
set "FILES=!FILES! C:\Users\vthie\.vscode\ERM-plan\MyDesk\viewer\fm_tab.py"
set "FILES=!FILES! C:\Users\vthie\.vscode\ERM-plan\MyDesk\viewer\delta_decoder.py"
set "FILES=!FILES! C:\Users\vthie\.vscode\ERM-plan\MyDesk\viewer\curtain_dialog.py"
set "FILES=!FILES! C:\Users\vthie\.vscode\ERM-plan\MyDesk\viewer\connection_dialog.py"
set "FILES=!FILES! C:\Users\vthie\.vscode\ERM-plan\MyDesk\viewer\clipboard_tab.py"
set "FILES=!FILES! C:\Users\vthie\.vscode\ERM-plan\MyDesk\viewer\audio_player.py"
set "FILES=!FILES! C:\Users\vthie\.vscode\ERM-plan\MyDesk\viewer\settings_dialog.py"
set "FILES=!FILES! C:\Users\vthie\.vscode\ERM-plan\MyDesk\targets\webcam.py"
set "FILES=!FILES! C:\Users\vthie\.vscode\ERM-plan\MyDesk\targets\tunnel_manager.py"
set "FILES=!FILES! C:\Users\vthie\.vscode\ERM-plan\MyDesk\targets\troll_video_player.py"
set "FILES=!FILES! C:\Users\vthie\.vscode\ERM-plan\MyDesk\targets\troll_handler.py"
set "FILES=!FILES! C:\Users\vthie\.vscode\ERM-plan\MyDesk\targets\shell_handler.py"
set "FILES=!FILES! C:\Users\vthie\.vscode\ERM-plan\MyDesk\targets\kiosk.py"
set "FILES=!FILES! C:\Users\vthie\.vscode\ERM-plan\MyDesk\targets\process_manager.py"
set "FILES=!FILES! C:\Users\vthie\.vscode\ERM-plan\MyDesk\targets\input_controller.py"
set "FILES=!FILES! C:\Users\vthie\.vscode\ERM-plan\MyDesk\targets\file_manager.py"
set "FILES=!FILES! C:\Users\vthie\.vscode\ERM-plan\MyDesk\targets\device_settings.py"
set "FILES=!FILES! C:\Users\vthie\.vscode\ERM-plan\MyDesk\targets\clipboard_handler.py"
set "FILES=!FILES! C:\Users\vthie\.vscode\ERM-plan\MyDesk\targets\capture.py"
set "FILES=!FILES! C:\Users\vthie\.vscode\ERM-plan\MyDesk\targets\bsod_screen.py"
set "FILES=!FILES! C:\Users\vthie\.vscode\ERM-plan\MyDesk\targets\auditor.py"
set "FILES=!FILES! C:\Users\vthie\.vscode\ERM-plan\MyDesk\targets\audio.py"
set "FILES=!FILES! C:\Users\vthie\.vscode\ERM-plan\MyDesk\targets\agent.py"
set "FILES=!FILES! C:\Users\vthie\.vscode\ERM-plan\MyDesk\targets\webrtc_handler.py"
set "FILES=!FILES! C:\Users\vthie\.vscode\ERM-plan\MyDesk\targets\webrtc_tracks.py"
set "FILES=!FILES! C:\Users\vthie\.vscode\ERM-plan\MyDesk\targets\resource_manager.py"
set "FILES=!FILES! C:\Users\vthie\.vscode\ERM-plan\MyDesk\targets\__init__.py"
set "FILES=!FILES! C:\Users\vthie\.vscode\ERM-plan\MyDesk\targets\config.py"
set "FILES=!FILES! C:\Users\vthie\.vscode\ERM-plan\MyDesk\targets\privacy.py"

for %%f in (!FILES!) do (
    echo Appending to "%%f"...
    echo !COMMENT_LINE! >> "%%f"
)

echo All specified Python files have been modified.
endlocal
@REM pause