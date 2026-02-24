module Api
  module V1
    class CharacterProfilesController < ApplicationController
      before_action :require_admin!, only: [:create, :update, :destroy]
      before_action :set_profile, only: [:show, :update, :destroy]

      def index
        profiles = CharacterProfile.all
        render json: profiles.map { |p| profile_json(p) }
      end

      def show
        render json: profile_json(@profile)
      end

      def create
        profile = CharacterProfile.new(profile_params)

        if profile.save
          render json: profile_json(profile), status: :created
        else
          render json: { error: profile.errors.full_messages.join(", ") }, status: :unprocessable_entity
        end
      end

      def update
        if @profile.update(profile_params)
          render json: profile_json(@profile)
        else
          render json: { error: @profile.errors.full_messages.join(", ") }, status: :unprocessable_entity
        end
      end

      def destroy
        @profile.destroy!
        render json: { ok: true }
      end

      private

      def set_profile
        @profile = CharacterProfile.find_by!(personality: params[:id])
      end

      def profile_params
        params.permit(
          :personality, :display_name,
          base_layer: [:row, :col, :sheet],
          hair_layer: [:row, :col, :sheet],
          eyes_layer: [:row, :col, :sheet],
          eyebrows_layer: [:row, :col, :sheet],
          mouth_layer: [:row, :col, :sheet],
          clothes_layer: [:row, :col, :sheet],
          bg_layer: [:row, :col, :sheet]
        )
      end

      def profile_json(profile)
        {
          personality: profile.personality,
          display_name: profile.display_name,
          base_layer: profile.base_layer,
          hair_layer: profile.hair_layer,
          eyes_layer: profile.eyes_layer,
          eyebrows_layer: profile.eyebrows_layer,
          mouth_layer: profile.mouth_layer,
          clothes_layer: profile.clothes_layer,
          bg_layer: profile.bg_layer,
          created_at: profile.created_at,
          updated_at: profile.updated_at
        }
      end
    end
  end
end
