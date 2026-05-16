# HackKnow — Android (Capacitor)

Wraps the HackKnow UI as a native Android app that talks to the FastAPI backend.

```bash
# 1) install Capacitor CLI
npm install -g @capacitor/cli

# 2) from project root
npx cap init "HackKnow" com.hackknow.aios --web-dir=ui
npx cap add android

# 3) point at this config
cp packaging/capacitor/capacitor.config.json .

# 4) build APK
cd android && ./gradlew assembleDebug
# → APK at android/app/build/outputs/apk/debug/app-debug.apk
```

For installable PWA without Capacitor, the UI already ships with a `manifest.webmanifest` + service worker — open `https://your-server/` in Chrome on Android and tap "Add to Home screen".
