require "net/http"
require "json"
require "uri"

class IdentityProxy
  TIMEOUT = 10

  def self.post(path, body: nil)
    base_url = ENV.fetch("IDENTITY_SERVICE_URL", "http://127.0.0.1:18791")
    uri = URI("#{base_url}#{path}")

    http = Net::HTTP.new(uri.host, uri.port)
    http.use_ssl = uri.scheme == "https"
    http.open_timeout = TIMEOUT
    http.read_timeout = TIMEOUT

    request = Net::HTTP::Post.new(uri)
    request["Content-Type"] = "application/json"

    service_secret = ENV["IDENTITY_SERVICE_SECRET"]
    request["X-Service-Secret"] = service_secret if service_secret.present?

    request.body = body.to_json if body.present?

    response = http.request(request)
    parsed = JSON.parse(response.body)

    { status: response.code.to_i, body: parsed }
  rescue StandardError => e
    Rails.logger.error("IdentityProxy error: #{e.class} - #{e.message}")
    { status: 502, body: { "error" => "Identity service unavailable: #{e.message}" } }
  end

  def self.get(path, headers: {})
    base_url = ENV.fetch("IDENTITY_SERVICE_URL", "http://127.0.0.1:18791")
    uri = URI("#{base_url}#{path}")

    http = Net::HTTP.new(uri.host, uri.port)
    http.use_ssl = uri.scheme == "https"
    http.open_timeout = TIMEOUT
    http.read_timeout = TIMEOUT

    request = Net::HTTP::Get.new(uri)
    request["Content-Type"] = "application/json"
    headers.each { |k, v| request[k] = v }

    service_secret = ENV["IDENTITY_SERVICE_SECRET"]
    request["X-Service-Secret"] = service_secret if service_secret.present?

    response = http.request(request)
    parsed = JSON.parse(response.body)

    { status: response.code.to_i, body: parsed }
  rescue StandardError => e
    Rails.logger.error("IdentityProxy error: #{e.class} - #{e.message}")
    { status: 502, body: { "error" => "Identity service unavailable: #{e.message}" } }
  end
end
