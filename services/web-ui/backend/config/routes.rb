Rails.application.routes.draw do
  # Auth stays at top level
  scope :auth do
    get "config", to: "auth#auth_config"
    post "dev-login", to: "auth#dev_login"
    get "login/:provider", to: "auth#login"
    get "callback/:provider", to: "auth#callback"
    post "logout", to: "auth#logout"
    get "me", to: "auth#me"
    post "link/:provider", to: "auth#link"
    delete "link/:provider", to: "auth#unlink"
  end

  namespace :api do
    namespace :v1 do
      resources :games, only: [:create, :show] do
        member do
          post :move
          post :ai_move
        end
      end
      get "lobby", to: "lobby#index"
      resources :history, only: [:index, :show]

      # Proxy endpoints (forwarded to Python gateway)
      resources :sessions, only: [:index, :show, :update, :destroy] do
        member do
          patch :archive
          patch :unarchive
        end
      end

      resources :memories, only: [:index, :show, :create, :update, :destroy] do
        member do
          get :history
          get :dynamics
          put :tags
        end
        collection do
          get :stats
          post :search
          get "tags/all", to: "memories#all_tags"
          get :export
          post "import", to: "memories#import_memories"
        end
      end

      get "graph/entities", to: "graph#entities"
      get "graph/entities/:name", to: "graph#entity"
      get "graph/search", to: "graph#search"
      get "graph/subgraph", to: "graph#subgraph"

      resources :intentions, only: [:index, :create, :update, :destroy]

      get "users/me", to: "users#me"
      put "users/me", to: "users#update_me"
      get "users/me/links", to: "users#links"

      get "admin/users", to: "admin#users"
      post "admin/users/:id/approve", to: "admin#approve"
      post "admin/users/:id/suspend", to: "admin#suspend"
      get "admin/users/pending/count", to: "admin#pending_count"
    end
  end

  # Health check
  get "up" => "rails/health#show", as: :rails_health_check

  # SPA fallback — must be last
  get "*path", to: "spa#index", constraints: ->(req) {
    !req.path.start_with?("/api/", "/auth/", "/cable", "/up")
  }
  root to: "spa#index"
end
