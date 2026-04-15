module Api
  module V1
    class GraphController < ApplicationController
      def entities
        result = GatewayProxy.forward(
          method: :get,
          path: "/api/v1/graph/entities",
          user_id: current_user.canonical_user_id,
          params: request.query_parameters
        )
        render json: result[:body], status: result[:status]
      end

      def entity
        result = GatewayProxy.forward(
          method: :get,
          path: "/api/v1/graph/entities/#{CGI.escape(params[:name])}",
          user_id: current_user.canonical_user_id
        )
        render json: result[:body], status: result[:status]
      end

      def search
        result = GatewayProxy.forward(
          method: :get,
          path: "/api/v1/graph/search",
          user_id: current_user.canonical_user_id,
          params: request.query_parameters
        )
        render json: result[:body], status: result[:status]
      end

      def subgraph
        result = GatewayProxy.forward(
          method: :get,
          path: "/api/v1/graph/subgraph",
          user_id: current_user.canonical_user_id,
          params: request.query_parameters
        )
        render json: result[:body], status: result[:status]
      end
    end
  end
end
