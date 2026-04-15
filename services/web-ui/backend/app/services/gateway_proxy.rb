require "net/http"
require "json"
require "uri"

class GatewayProxy
  TIMEOUT = 15

  def self.forward(method:, path:, user_id:, params: {}, body: nil)
    base_url = ENV.fetch("CLARA_GATEWAY_API_URL", "http://127.0.0.1:18790")
    uri = URI("#{base_url}#{path}")

    # Append query params for GET/DELETE requests
    if params.present? && %i[get delete].include?(method)
      uri.query = URI.encode_www_form(params)
    end

    http = Net::HTTP.new(uri.host, uri.port)
    http.use_ssl = uri.scheme == "https"
    http.open_timeout = TIMEOUT
    http.read_timeout = TIMEOUT

    request = build_request(method, uri, body)
    request["Content-Type"] = "application/json"
    request["X-Canonical-User-Id"] = user_id.to_s

    gateway_secret = ENV["CLARA_GATEWAY_SECRET"]
    request["X-Gateway-Secret"] = gateway_secret if gateway_secret.present?

    response = http.request(request)

    parsed_body = begin
      JSON.parse(response.body)
    rescue JSON::ParserError
      { "error" => "Invalid JSON response from gateway", "raw" => response.body }
    end

    { status: response.code.to_i, body: parsed_body, headers: response.to_hash }
  rescue JSON::ParserError => e
    Rails.logger.error("GatewayProxy JSON error: #{e.message}")
    { status: 502, body: { "error" => "Bad gateway: invalid JSON response" }, headers: {} }
  rescue StandardError => e
    Rails.logger.error("GatewayProxy error: #{e.class} - #{e.message}")
    { status: 502, body: { "error" => "Bad gateway: #{e.message}" }, headers: {} }
  end

  private_class_method def self.build_request(method, uri, body)
    klass = case method
    when :get    then Net::HTTP::Get
    when :post   then Net::HTTP::Post
    when :put    then Net::HTTP::Put
    when :patch  then Net::HTTP::Patch
    when :delete then Net::HTTP::Delete
    else raise ArgumentError, "Unsupported HTTP method: #{method}"
    end

    request = klass.new(uri)
    request.body = body.to_json if body.present?
    request
  end
end
