import Foundation

enum AppConfig {
    /// The hosted Personal CFO URL -- see the main repo's README under
    /// "Hosting it for other people". Must be a real HTTPS URL before
    /// you ship this anywhere: App Transport Security blocks plain HTTP
    /// by default (as it should -- there is no exception configured for
    /// it in Info.plist), and gating a plaintext connection behind Face
    /// ID would defeat the point of either.
    ///
    /// Replace this placeholder before building.
    static let baseURL = URL(string: "https://REPLACE-WITH-YOUR-HOSTED-URL.onrender.com")!
}
