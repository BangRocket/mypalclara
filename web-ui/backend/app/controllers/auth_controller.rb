class AuthController < ApplicationController
  skip_before_action :authenticate_user!, only: [:callback, :login]

  def login
    redirect_uri = "#{request.base_url}/auth/callback"
    clara_url = ENV.fetch("CLARA_AUTH_URL", "https://mypalclara.com")
    redirect_to "#{clara_url}/auth/game-redirect?redirect_uri=#{CGI.escape(redirect_uri)}",
      allow_other_host: true
  end

  def callback
    token = params[:token]
    payload = decode_game_token(token)

    if payload.nil?
      redirect_to root_path, alert: "Authentication failed. Please try again."
      return
    end

    user = User.find_or_create_by!(canonical_user_id: payload["sub"]) do |u|
      u.display_name = payload["name"]
      u.avatar_url = payload["avatar"]
    end

    user.update(
      display_name: payload["name"],
      avatar_url: payload["avatar"]
    )

    session[:user_id] = user.id
    redirect_to root_path
  end

  def logout
    reset_session
    redirect_to root_path
  end

  private

  def decode_game_token(token)
    secret = ENV.fetch("CLARA_JWT_SECRET")
    JWT.decode(
      token,
      secret,
      true,
      algorithm: "HS256",
      aud: "games.mypalclara.com",
      verify_aud: true,
    ).first
  rescue JWT::DecodeError, JWT::ExpiredSignature, JWT::InvalidAudError, KeyError
    nil
  end
end
