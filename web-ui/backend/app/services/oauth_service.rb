require "net/http"
require "json"
require "uri"

class OauthService
  PROVIDERS = {
    "discord" => {
      authorize_url: "https://discord.com/api/oauth2/authorize",
      token_url: "https://discord.com/api/oauth2/token",
      user_url: "https://discord.com/api/users/@me",
      scope: "identify email",
      client_id_env: "DISCORD_OAUTH_CLIENT_ID",
      client_secret_env: "DISCORD_OAUTH_CLIENT_SECRET",
      redirect_uri_env: "DISCORD_OAUTH_REDIRECT_URI"
    },
    "google" => {
      authorize_url: "https://accounts.google.com/o/oauth2/v2/auth",
      token_url: "https://oauth2.googleapis.com/token",
      user_url: "https://www.googleapis.com/oauth2/v2/userinfo",
      scope: "openid email profile",
      client_id_env: "GOOGLE_OAUTH_CLIENT_ID",
      client_secret_env: "GOOGLE_OAUTH_CLIENT_SECRET",
      redirect_uri_env: "GOOGLE_OAUTH_REDIRECT_URI"
    }
  }.freeze

  def self.authorize_url(provider)
    cfg = PROVIDERS.fetch(provider)
    params = {
      client_id: ENV[cfg[:client_id_env]],
      redirect_uri: ENV[cfg[:redirect_uri_env]],
      response_type: "code",
      scope: cfg[:scope]
    }
    "#{cfg[:authorize_url]}?#{URI.encode_www_form(params)}"
  end

  def self.exchange_code(provider, code)
    cfg = PROVIDERS.fetch(provider)
    uri = URI(cfg[:token_url])
    response = Net::HTTP.post_form(uri,
      client_id: ENV[cfg[:client_id_env]],
      client_secret: ENV[cfg[:client_secret_env]],
      grant_type: "authorization_code",
      code: code,
      redirect_uri: ENV[cfg[:redirect_uri_env]]
    )
    JSON.parse(response.body)
  end

  def self.fetch_user(provider, access_token)
    cfg = PROVIDERS.fetch(provider)
    uri = URI(cfg[:user_url])
    req = Net::HTTP::Get.new(uri)
    req["Authorization"] = "Bearer #{access_token}"
    response = Net::HTTP.start(uri.hostname, uri.port, use_ssl: true) { |http| http.request(req) }
    JSON.parse(response.body)
  end

  def self.available_providers
    PROVIDERS.keys.select { |p| ENV[PROVIDERS[p][:client_id_env]].present? }
  end
end
