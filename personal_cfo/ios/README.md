# Personal CFO -- iOS wrapper

A thin native wrapper: a WKWebView pointed at your hosted Personal CFO
app, gated by Face ID / Touch ID before it loads. All the actual
functionality is the Streamlit app running on your server (see the main
repo's README, "Hosting it for other people") -- this project exists
to (a) give people a real app icon to tap instead of a bookmark, and
(b) add device-level biometric locking that a plain website in Safari
can't offer.

## Important: this project has not been built or run

Everything in `PersonalCFO/` is real, complete Swift source -- but it was
written without access to Xcode, a Mac, or a simulator, so it has never
actually been compiled. There is deliberately no `.xcodeproj` file here:
Xcode's project file format is intricate (an internally-consistent object
graph with generated UUIDs) and a hand-written one risks being subtly
broken in a way that's hard to debug without Xcode itself to fix it.
Instead, generate the project with Xcode -- which does that part
correctly by construction -- and drop these files in. Expect small build
errors on the first attempt (an API signature drift between Swift/iOS
SDK versions, a typo) and to need to fix them yourself or hand them back
to me to fix once you can see the actual compiler output.

## What you need first

- A Mac with Xcode installed (free from the Mac App Store).
- An [Apple Developer Program](https://developer.apple.com/programs/)
  membership ($99/year) -- required to run on a physical device and to
  submit to the App Store at all. Not required just to build and run in
  the iOS Simulator.
- Your Personal CFO app already hosted somewhere with a real HTTPS URL
  (see the main README) -- this wrapper has nothing to point at otherwise.

## Setup

1. **Create the Xcode project.** Xcode -> File -> New -> Project -> iOS ->
   App. Product Name: `PersonalCFO`. Interface: **SwiftUI**. Language:
   **Swift**. Uncheck "Include Tests" (or leave it, doesn't matter).
   Save it anywhere -- not necessarily inside this repo.

2. **Replace the generated files with these ones.** Xcode creates
   `PersonalCFOApp.swift` and `ContentView.swift` for you -- delete their
   contents and paste in the versions from this folder, or just delete
   the generated files and drag all five `.swift` files from
   `ios/PersonalCFO/` into the Xcode project navigator (check "Copy items
   if needed").

3. **Set your hosted URL.** Open `Config.swift` and replace the
   placeholder with your real HTTPS URL from Render (or wherever you
   hosted it).

4. **Add the Face ID usage description.** Select the project in the
   navigator -> your target -> **Info** tab -> add a row: key
   `Privacy - Face ID Usage Description` (this is `NSFaceIDUsageDescription`
   under the hood), value from `Info-additions.plist` in this folder.
   Skipping this makes the app crash the moment it asks for Face ID.

5. **Set your Bundle Identifier and Signing Team.** Project navigator ->
   target -> **Signing & Capabilities** tab. Bundle ID needs to be unique
   (reverse-DNS style, e.g. `com.yourname.personalcfo`); Team is your
   Apple Developer account, needed to run on a real device or submit to
   the App Store.

6. **Build and run.**
   - **Simulator:** works without a paid developer account. Face ID in
     the Simulator needs to be explicitly enabled: Simulator menu ->
     Features -> Face ID -> Enrolled, then (once the app requests it)
     Features -> Face ID -> Matching Face to simulate a successful scan.
   - **Real device:** needs the paid developer account from step 5, your
     device registered to it, and a provisioning profile (Xcode usually
     handles this automatically once signing is configured).

## What this wrapper does and doesn't do

- **Does:** show your hosted app in a native container, ask for Face ID/
  Touch ID before displaying it, re-lock whenever the app goes to the
  background, keep you signed in between launches (cookies persist via
  `WKWebsiteDataStore.default()`).
- **Does not:** work offline, send push notifications, do anything the
  hosted web app itself doesn't already do. The Face ID gate here is a
  *device-local* lock layered on top of -- not a replacement for -- the
  hosted app's own login (its shared password or Google Sign-In). Someone
  who unlocks your phone with your Face ID still needs the app's own
  credentials if you have password protection or Google Sign-In turned
  on there too; conversely, Face ID here doesn't authenticate you *to*
  the server at all, it only decides whether this phone shows the page.

## App Store review risk: Guideline 4.2 (Minimum Functionality)

Apple's App Review guidelines call out bare website wrappers as a common
rejection reason -- "a web site wrapped as an app is not sufficient." The
native Face ID gate, the persistent native app icon/launch experience,
and (if you build them later) any genuinely native features push this
away from "bare wrapper," but there's no guarantee of approval. See the
main App Store checklist (`../APP_STORE_CHECKLIST.md`) for more on this
specific risk and what mitigates it.
