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

      payload = JwtService.decode(token)
      return reject_unauthorized_connection unless payload

      user = User.find_by(canonical_user_id: payload["sub"])
      return reject_unauthorized_connection unless user
      user
    end
  end
end
