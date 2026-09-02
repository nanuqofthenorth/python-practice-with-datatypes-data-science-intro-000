import SwiftUI

struct ContentView: View {
    @StateObject private var biometrics = BiometricAuthManager()
    @State private var isLoading = false
    @State private var loadError: String?
    @Environment(\.scenePhase) private var scenePhase

    var body: some View {
        Group {
            if biometrics.isUnlocked {
                unlockedContent
            } else {
                lockScreen
            }
        }
        .onAppear {
            biometrics.authenticate()
        }
        .onChange(of: scenePhase) { newPhase in
            // Re-lock whenever the app leaves the foreground -- financial
            // data shouldn't stay visible in the app switcher preview or
            // remain unlocked after returning from background unattended.
            if newPhase == .background {
                biometrics.lock()
            } else if newPhase == .active && !biometrics.isUnlocked {
                biometrics.authenticate()
            }
        }
    }

    private var unlockedContent: some View {
        ZStack {
            WebView(url: AppConfig.baseURL, isLoading: $isLoading, loadError: $loadError)

            if isLoading {
                ProgressView()
            }

            if let loadError {
                VStack(spacing: 12) {
                    Text("Couldn't load Personal CFO")
                        .font(.headline)
                    Text(loadError)
                        .font(.caption)
                        .multilineTextAlignment(.center)
                        .foregroundColor(.secondary)
                    Button("Retry") {
                        self.loadError = nil
                    }
                    .buttonStyle(.borderedProminent)
                }
                .padding()
                .background(.ultraThinMaterial)
                .cornerRadius(12)
                .padding()
            }
        }
    }

    private var lockScreen: some View {
        VStack(spacing: 16) {
            Image(systemName: "lock.shield")
                .font(.system(size: 48))
                .foregroundColor(.secondary)
            Text("Personal CFO")
                .font(.title2)
                .bold()
            if let authError = biometrics.authError {
                Text(authError)
                    .font(.caption)
                    .foregroundColor(.red)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal)
            }
            Button("Unlock") {
                biometrics.authenticate()
            }
            .buttonStyle(.borderedProminent)
        }
        .padding()
    }
}

#Preview {
    ContentView()
}
