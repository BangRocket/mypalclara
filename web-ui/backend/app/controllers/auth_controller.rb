class AuthController < ApplicationController
  # Auth endpoints don't require existing authentication
  skip_before_action :authenticate_user!, only: [:config, :dev_login, :login, :callback, :logout]

  def config
    render json: {
      dev_mode: ENV["WEB_DEV_MODE"] == "true",
      providers: OauthService.available_providers
    }
  end

  def dev_login
    unless ENV["WEB_DEV_MODE"] == "true"
      return render json: { error: "Dev mode disabled" }, status: :forbidden
    end

    user = User.find_or_create_by(canonical_user_id: "00000000-0000-0000-0000-000000000dev") do |u|
      u.display_name = ENV.fetch("WEB_DEV_USER_NAME", "Dev User")
    end

    token = JwtService.encode(user.canonical_user_id, name: user.display_name)
    set_auth_cookie(token)
    render json: { token: token, user: user_response(user) }
  end

  def login
    provider = params[:provider]
    unless OauthService::PROVIDERS.key?(provider)
      return render json: { error: "Unknown provider" }, status: :bad_request
    end

    url = OauthService.authorize_url(provider)
    render json: { url: url }
  end

  def callback
    provider = params[:provider]
    code = params[:code]

    unless OauthService::PROVIDERS.key?(provider) && code.present?
      return render json: { error: "Invalid callback" }, status: :bad_request
    end

    token_data = OauthService.exchange_code(provider, code)
    unless token_data["access_token"]
      return render json: { error: "OAuth token exchange failed" }, status: :unprocessable_entity
    end

    profile = OauthService.fetch_user(provider, token_data["access_token"])
    user = find_or_create_user(provider, profile)

    jwt = JwtService.encode(user.canonical_user_id, name: user.display_name)
    set_auth_cookie(jwt)
    render json: { token: jwt, user: user_response(user) }
  end

  def logout
    cookies.delete(:access_token)
    render json: { ok: true }
  end

  def me
    render json: user_response(current_user)
  end

  def link
    # Link additional OAuth account to existing user
    provider = params[:provider]
    code = params[:code]

    token_data = OauthService.exchange_code(provider, code)
    profile = OauthService.fetch_user(provider, token_data["access_token"])

    # Tell gateway to create platform link
    GatewayProxy.forward(
      method: :post, path: "/api/v1/users/link",
      user_id: current_user.canonical_user_id,
      body: { provider: provider, profile: profile }
    )

    render json: { ok: true }
  end

  def unlink
    provider = params[:provider]
    GatewayProxy.forward(
      method: :delete, path: "/api/v1/users/link/#{provider}",
      user_id: current_user.canonical_user_id
    )
    render json: { ok: true }
  end

  private

  def set_auth_cookie(token)
    cookies[:access_token] = {
      value: token,
      httponly: true,
      secure: Rails.env.production?,
      same_site: :lax,
      expires: JwtService::EXPIRE_MINUTES.minutes.from_now
    }
  end

  def user_response(user)
    {
      id: user.canonical_user_id,
      display_name: user.display_name,
      avatar_url: user.avatar_url
    }
  end

  def find_or_create_user(provider, profile)
    platform_id = profile["id"]
    display_name = profile["global_name"] || profile["username"] || profile["name"] || "User"

    # Try to find existing user (check by creating a lookup in gateway)
    user = User.find_by(canonical_user_id: platform_id)

    unless user
      user = User.create!(
        canonical_user_id: SecureRandom.uuid,
        display_name: display_name,
        avatar_url: extract_avatar(provider, profile)
      )
    end

    # Ensure user exists in main DB via gateway
    GatewayProxy.forward(
      method: :post, path: "/api/v1/users/ensure",
      user_id: user.canonical_user_id,
      body: {
        provider: provider,
        platform_user_id: platform_id,
        display_name: display_name
      }
    )

    user
  end

  def extract_avatar(provider, profile)
    case provider
    when "discord"
      avatar = profile["avatar"]
      avatar ? "https://cdn.discordapp.com/avatars/#{profile["id"]}/#{avatar}.png" : nil
    when "google"
      profile["picture"]
    end
  end
end
