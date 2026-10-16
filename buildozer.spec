[app]
title = Trainer OT EB
package.name = flet_trainer_app
package.domain = org.trainer
source.dir = .
source.include_exts = py,png,jpg,kv,atlas,json
version = 2.0.0
requirements = python3,flet,requests,urllib3,certifi,idna,charset-normalizer

orientation = portrait
fullscreen = 1
android.archs = arm64-v8a, armeabi-v7a
android.allow_backup = False

# Андроид разрешения и SDK (Java 17 совместимый)
android.api = 34
android.minapi = 21
android.ndk = 25b
android.sdk_build_tools = 34.0.0
android.private_storage = True

# Иконка приложения (раскомментируй, если добавишь icon.png в корень)
# icon.filename = %(source.dir)s/icon.png

[buildozer]
log_level = 2
warn_on_root = 1
