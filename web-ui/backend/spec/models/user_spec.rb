require "rails_helper"

RSpec.describe User, type: :model do
  describe "validations" do
    it "requires canonical_user_id" do
      user = User.new(display_name: "Test")
      expect(user).not_to be_valid
      expect(user.errors[:canonical_user_id]).to include("can't be blank")
    end

    it "requires display_name" do
      user = User.new(canonical_user_id: "abc-123")
      expect(user).not_to be_valid
      expect(user.errors[:display_name]).to include("can't be blank")
    end

    it "enforces unique canonical_user_id" do
      create(:user, canonical_user_id: "abc-123")
      duplicate = build(:user, canonical_user_id: "abc-123")
      expect(duplicate).not_to be_valid
    end

    it "creates a valid user with required fields" do
      user = build(:user)
      expect(user).to be_valid
    end
  end
end
