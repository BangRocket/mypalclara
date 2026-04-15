# Stage 1: Build React frontend
FROM node:22-slim AS frontend
WORKDIR /app/frontend
COPY frontend/package.json frontend/pnpm-lock.yaml* frontend/package-lock.json* ./
RUN npm install --frozen-lockfile 2>/dev/null || npx pnpm install --frozen-lockfile 2>/dev/null || npm install
COPY frontend/ .
RUN npm run build

# Stage 2: Ruby base
FROM ruby:3.4.8-slim AS base
RUN apt-get update -qq && apt-get install --no-install-recommends -y \
    libpq5 curl && \
    rm -rf /var/lib/apt/lists /var/cache/apt/archives

WORKDIR /app
ENV RAILS_ENV=production \
    BUNDLE_WITHOUT="development:test"

# Stage 3: Build Ruby dependencies
FROM base AS build
RUN apt-get update -qq && apt-get install --no-install-recommends -y \
    build-essential libpq-dev pkg-config libyaml-dev && \
    rm -rf /var/lib/apt/lists /var/cache/apt/archives

COPY backend/Gemfile backend/Gemfile.lock ./
RUN bundle install && \
    rm -rf ~/.bundle/ "${BUNDLE_PATH}"/ruby/*/cache

COPY backend/ .
RUN bundle exec bootsnap precompile app/ lib/

# Stage 4: Final
FROM base
COPY --from=build /usr/local/bundle /usr/local/bundle
COPY --from=build /app /app
COPY --from=frontend /app/frontend/dist /app/public/

# Ensure entrypoint is executable
RUN chmod +x /app/bin/docker-entrypoint

# Non-root user
RUN groupadd --system --gid 1000 rails && \
    useradd rails --uid 1000 --gid 1000 --create-home --shell /bin/bash && \
    chown -R rails:rails /app
USER rails:rails

EXPOSE 3000
CMD ["/app/bin/docker-entrypoint"]
