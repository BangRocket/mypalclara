module Api
  module V1
    class FilesystemController < ApplicationController
      def tree
        entries = FileSystemEntry.for_user(current_user).order(:created_at)
        render json: entries.map { |e| serialize(e) }
      end

      def create
        entry = current_user.file_system_entries.build(entry_params)
        if entry.save
          render json: serialize(entry), status: :created
        else
          render json: { errors: entry.errors.full_messages }, status: :unprocessable_entity
        end
      end

      def update
        entry = current_user.file_system_entries.find(params[:id])
        if entry.update(entry_params)
          render json: serialize(entry)
        else
          render json: { errors: entry.errors.full_messages }, status: :unprocessable_entity
        end
      end

      def destroy
        entry = current_user.file_system_entries.find(params[:id])
        entry.destroy!
        render json: { ok: true }
      end

      private

      def entry_params
        params.permit(:name, :parent_id, :entry_type, :extension, :app_id,
                       :content, :icon, :disable_delete, :disable_copy,
                       icon_position: [:x, :y])
      end

      def serialize(entry)
        {
          id: entry.id,
          name: entry.name,
          parent_id: entry.parent_id,
          type: entry.entry_type,
          extension: entry.extension,
          app_id: entry.app_id,
          content: entry.content,
          icon_position: entry.icon_position,
          icon: entry.icon,
          disable_delete: entry.disable_delete,
          disable_copy: entry.disable_copy,
          children: entry.children.pluck(:id),
          created_at: entry.created_at,
          updated_at: entry.updated_at,
        }
      end
    end
  end
end
