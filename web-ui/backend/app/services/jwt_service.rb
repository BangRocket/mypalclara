class JwtService
  SECRET = ENV.fetch("WEB_SECRET_KEY", "change-me-in-production")
  EXPIRE_MINUTES = ENV.fetch("WEB_JWT_EXPIRE_MINUTES", "1440").to_i

  def self.encode(canonical_user_id, extra_claims = {})
    payload = {
      sub: canonical_user_id,
      exp: EXPIRE_MINUTES.minutes.from_now.to_i,
      iat: Time.now.to_i
    }.merge(extra_claims)
    JWT.encode(payload, SECRET, "HS256")
  end

  def self.decode(token)
    JWT.decode(token, SECRET, true, algorithm: "HS256").first
  rescue JWT::DecodeError, JWT::ExpiredSignature, JWT::VerificationError
    nil
  end
end
