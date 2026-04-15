module Api
  module V1
    class MemoriesController < ApplicationController
      def index
        result = GatewayProxy.forward(
          method: :get,
          path: "/api/v1/memories",
          user_id: current_user.canonical_user_id,
          params: request.query_parameters
        )
        render json: result[:body], status: result[:status]
      end

      def show
        result = GatewayProxy.forward(
          method: :get,
          path: "/api/v1/memories/#{params[:id]}",
          user_id: current_user.canonical_user_id
        )
        render json: result[:body], status: result[:status]
      end

      def create
        result = GatewayProxy.forward(
          method: :post,
          path: "/api/v1/memories",
          user_id: current_user.canonical_user_id,
          body: proxy_body
        )
        render json: result[:body], status: result[:status]
      end

      def update
        result = GatewayProxy.forward(
          method: :put,
          path: "/api/v1/memories/#{params[:id]}",
          user_id: current_user.canonical_user_id,
          body: proxy_body
        )
        render json: result[:body], status: result[:status]
      end

      def destroy
        result = GatewayProxy.forward(
          method: :delete,
          path: "/api/v1/memories/#{params[:id]}",
          user_id: current_user.canonical_user_id
        )
        render json: result[:body], status: result[:status]
      end

      def history
        result = GatewayProxy.forward(
          method: :get,
          path: "/api/v1/memories/#{params[:id]}/history",
          user_id: current_user.canonical_user_id
        )
        render json: result[:body], status: result[:status]
      end

      def dynamics
        result = GatewayProxy.forward(
          method: :get,
          path: "/api/v1/memories/#{params[:id]}/dynamics",
          user_id: current_user.canonical_user_id
        )
        render json: result[:body], status: result[:status]
      end

      def search
        result = GatewayProxy.forward(
          method: :post,
          path: "/api/v1/memories/search",
          user_id: current_user.canonical_user_id,
          body: proxy_body
        )
        render json: result[:body], status: result[:status]
      end

      def stats
        result = GatewayProxy.forward(
          method: :get,
          path: "/api/v1/memories/stats",
          user_id: current_user.canonical_user_id
        )
        render json: result[:body], status: result[:status]
      end

      def tags
        result = GatewayProxy.forward(
          method: :put,
          path: "/api/v1/memories/#{params[:id]}/tags",
          user_id: current_user.canonical_user_id,
          body: proxy_body
        )
        render json: result[:body], status: result[:status]
      end

      def all_tags
        result = GatewayProxy.forward(
          method: :get,
          path: "/api/v1/memories/tags/all",
          user_id: current_user.canonical_user_id
        )
        render json: result[:body], status: result[:status]
      end

      def export
        result = GatewayProxy.forward(
          method: :get,
          path: "/api/v1/memories/export",
          user_id: current_user.canonical_user_id
        )
        render json: result[:body], status: result[:status]
      end

      def import_memories
        result = GatewayProxy.forward(
          method: :post,
          path: "/api/v1/memories/import",
          user_id: current_user.canonical_user_id,
          body: proxy_body
        )
        render json: result[:body], status: result[:status]
      end

      private

      def proxy_body
        params.except(:controller, :action, :id, :format).permit!.to_h
      end
    end
  end
end
