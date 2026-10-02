import Foundation
import Vision
import AppKit
let url = URL(fileURLWithPath: CommandLine.arguments[1])
let request = VNDetectBarcodesRequest()
request.symbologies = [.qr]
try VNImageRequestHandler(url: url).perform([request])
for result in request.results ?? [] {
    print(result.payloadStringValue ?? "")
}
