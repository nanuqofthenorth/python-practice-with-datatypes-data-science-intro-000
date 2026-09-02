import Foundation
import LocalAuthentication

/// Wraps Face ID / Touch ID via LocalAuthentication to gate access to the
/// WebView on this device. This is a LOCAL, on-device lock screen only --
/// it is separate from, and in addition to, whatever login the hosted
/// app itself uses (its own shared password, or Google Sign-In). Nothing
/// about a successful Face ID scan is sent to the server; it only
/// decides whether this app shows the WebView at all on this phone.
final class BiometricAuthManager: ObservableObject {
    @Published var isUnlocked = false
    @Published var authError: String?

    func authenticate() {
        let context = LAContext()
        var error: NSError?

        if context.canEvaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, error: &error) {
            let reason = "Unlock Personal CFO"
            context.evaluatePolicy(.deviceOwnerAuthenticationWithBiometrics, localizedReason: reason) { [weak self] success, evaluateError in
                DispatchQueue.main.async {
                    if success {
                        self?.isUnlocked = true
                        self?.authError = nil
                    } else {
                        self?.authError = evaluateError?.localizedDescription ?? "Authentication failed."
                    }
                }
            }
        } else {
            // No biometrics enrolled, or Face ID/Touch ID unavailable on
            // this device (or denied in Settings) -- fall back to the
            // device passcode rather than locking the user out entirely.
            authenticateWithPasscodeFallback()
        }
    }

    private func authenticateWithPasscodeFallback() {
        let context = LAContext()
        var error: NSError?
        guard context.canEvaluatePolicy(.deviceOwnerAuthentication, error: &error) else {
            DispatchQueue.main.async {
                self.authError = "No Face ID, Touch ID, or device passcode is set up. "
                    + "Set one up in iOS Settings to use this app."
            }
            return
        }
        context.evaluatePolicy(.deviceOwnerAuthentication, localizedReason: "Unlock Personal CFO") { [weak self] success, evaluateError in
            DispatchQueue.main.async {
                if success {
                    self?.isUnlocked = true
                    self?.authError = nil
                } else {
                    self?.authError = evaluateError?.localizedDescription ?? "Authentication failed."
                }
            }
        }
    }

    func lock() {
        isUnlocked = false
    }
}
