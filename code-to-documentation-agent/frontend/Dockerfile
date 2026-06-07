FROM node:20-alpine as build

WORKDIR /app

COPY . .

# Install dependencies
RUN npm install

ENV PUBLIC_URL=/documentation

# Build the app
RUN npm run build

# Production stage
FROM nginx:alpine

# Copy built assets from build stage
COPY --from=build /app/build /usr/share/nginx/html

# Copy custom nginx configuration
COPY --from=build /app/nginx.conf /etc/nginx/conf.d/default.conf

# Copy nginx entrypoint script
COPY --from=build /app/nginx-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

# Expose port
EXPOSE 80

# Use custom entrypoint
ENTRYPOINT ["/docker-entrypoint.sh"]