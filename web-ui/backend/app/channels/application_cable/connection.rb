module ApplicationCable
  class Connection < ActionCable::Connection::Base
    identified_by :current_user

    def connect
      self.current_user = find_verified_user
    end

    private

    def find_verified_user
      token = request.params[:token] || cookies[:access_token]
      return reject_unauthorized_connection unless token

      secret = ENV.fetch("WEB_SECRET_KEY", "change-me-in-production")
      payload = JWT.decode(token, secret, true, algorithm: "HS256").first
      user = User.find_by(canonical_user_id: payload["sub"])
      return reject_unauthorized_connection unless user
      user
    rescue JWT::DecodeError
      reject_unauthorized_connection
    end
  end
end
