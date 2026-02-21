class AuthController < ApplicationController
  skip_before_action :authenticate_user!, only: [:auth_config, :dev_login, :login, :callback, :logout]

  def auth_config
    result = IdentityProxy.get("/auth/config")
    render json: result[:body], status: result[:status]
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
    result = IdentityProxy.post("/oauth/authorize", body: { provider: params[:provider] })
    render json: result[:body], status: result[:status]
  end

  def callback
    provider = params[:provider]
    code = params[:code]

    unless provider.present? && code.present?
      return render json: { error: "Invalid callback" }, status: :bad_request
    end

    result = IdentityProxy.post("/oauth/callback", body: { provider: provider, code: code })

    unless result[:status] == 200
      if request.xhr? || request.content_type&.include?("json")
        return render json: result[:body], status: result[:status]
      else
        return redirect_to "/login?error=oauth_failed", allow_other_host: false
      end
    end

    identity_user = result[:body]
    jwt = identity_user["token"]

    # Find or create local Rails user
    user = User.find_or_create_by!(canonical_user_id: identity_user.dig("user", "id")) do |u|
      u.display_name = identity_user.dig("user", "display_name") || "User"
      u.avatar_url = identity_user.dig("user", "avatar_url")
    end

    # Update display name and avatar if changed
    changed = false
    new_name = identity_user.dig("user", "display_name")
    if new_name.present? && new_name != user.display_name
      user.display_name = new_name
      changed = true
    end
    new_avatar = identity_user.dig("user", "avatar_url")
    if new_avatar.present? && new_avatar != user.avatar_url
      user.avatar_url = new_avatar
      changed = true
    end
    user.save! if changed

    set_auth_cookie(jwt)

    if request.xhr? || request.content_type&.include?("json")
      render json: { token: jwt, user: user_response(user) }
    else
      redirect_to "/", allow_other_host: false
    end
  end

  def logout
    cookies.delete(:access_token)
    render json: { ok: true }
  end

  def me
    render json: user_response(current_user)
  end

  def link
    provider = params[:provider]
    code = params[:code]

    result = IdentityProxy.post("/oauth/callback", body: { provider: provider, code: code })
    unless result[:status] == 200
      return render json: result[:body], status: result[:status]
    end

    render json: { ok: true }
  end

  def unlink
    # TODO: add unlink endpoint to identity service
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
end
