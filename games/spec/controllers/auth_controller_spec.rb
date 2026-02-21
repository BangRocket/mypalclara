require "rails_helper"

RSpec.describe AuthController, type: :controller do
  describe "GET #callback" do
    let(:secret_key) { "test-secret-key" }
    let(:valid_token) do
      payload = {
        "sub" => "canonical-user-123",
        "name" => "Joshua",
        "avatar" => "https://example.com/avatar.png",
        "aud" => "games.mypalclara.com",
        "iat" => Time.now.to_i,
        "exp" => 5.minutes.from_now.to_i,
      }
      JWT.encode(payload, secret_key, "HS256")
    end

    before do
      ENV["CLARA_JWT_SECRET"] = secret_key
    end

    it "creates a user and sets session from valid token" do
      get :callback, params: { token: valid_token }
      expect(response).to redirect_to(root_path)
      expect(User.find_by(canonical_user_id: "canonical-user-123")).to be_present
      expect(session[:user_id]).to be_present
    end

    it "finds existing user on repeat login" do
      user = create(:user, canonical_user_id: "canonical-user-123")
      get :callback, params: { token: valid_token }
      expect(User.where(canonical_user_id: "canonical-user-123").count).to eq(1)
      expect(session[:user_id]).to eq(user.id)
    end

    it "rejects expired tokens" do
      expired_payload = {
        "sub" => "user-123",
        "name" => "Test",
        "aud" => "games.mypalclara.com",
        "iat" => 10.minutes.ago.to_i,
        "exp" => 5.minutes.ago.to_i,
      }
      token = JWT.encode(expired_payload, secret_key, "HS256")
      get :callback, params: { token: token }
      expect(response).to redirect_to(root_path)
      expect(flash[:alert]).to be_present
    end

    it "rejects tokens with wrong audience" do
      wrong_aud_payload = {
        "sub" => "user-123",
        "name" => "Test",
        "aud" => "evil.com",
        "iat" => Time.now.to_i,
        "exp" => 5.minutes.from_now.to_i,
      }
      token = JWT.encode(wrong_aud_payload, secret_key, "HS256")
      get :callback, params: { token: token }
      expect(response).to redirect_to(root_path)
      expect(flash[:alert]).to be_present
    end
  end
end
