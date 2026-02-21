# Puma production configuration for Clara Games
# Bind to Unix socket for Nginx reverse proxy

workers ENV.fetch("WEB_CONCURRENCY", 2)
threads_count = ENV.fetch("RAILS_MAX_THREADS", 5).to_i
threads threads_count, threads_count

bind "unix:///var/www/clara-games/tmp/sockets/puma.sock"
environment "production"
pidfile "/var/www/clara-games/tmp/pids/puma.pid"

# Allow puma to be restarted by systemd
plugin :tmp_restart
