class FileSystemEntry < ApplicationRecord
  belongs_to :user
  belongs_to :parent, class_name: "FileSystemEntry", optional: true
  has_many :children, class_name: "FileSystemEntry", foreign_key: :parent_id, dependent: :destroy

  validates :name, presence: true
  validates :entry_type, inclusion: { in: %w[file directory app-shortcut] }
  validates :name, uniqueness: { scope: [:user_id, :parent_id] }

  scope :for_user, ->(user) { where(user: user) }
end
