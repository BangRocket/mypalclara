class ApplicationController < ActionController::API
  before_action :authenticate_user!

  private

  def authenticate_user!
    token = extract_token
    unless token
      render json: { error: "Authentication required" }, status: :unauthorized
      return
    end

    payload = decode_jwt(token)
    unless payload
      render json: { error: "Invalid or expired token" }, status: :unauthorized
      return
    end

    @current_user = User.find_or_create_by!(canonical_user_id: payload["sub"]) do |u|
      u.display_name = payload["name"] || "User"
    end
  end

  def current_user
    @current_user
  end

  def extract_token
    # Check Authorization header first
    auth_header = request.headers["Authorization"]
    if auth_header&.start_with?("Bearer ")
      return auth_header.sub("Bearer ", "")
    end

    # Fall back to cookie
    cookies[:access_token]
  end

  def decode_jwt(token)
    JwtService.decode(token)
  end
end
