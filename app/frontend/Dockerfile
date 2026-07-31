# Stage 1: Build React App
FROM node:20-alpine AS build

WORKDIR /app

# Copy package manifests & install dependencies
COPY package*.json ./
RUN npm ci

# Copy full application code & build for production
COPY . .
RUN npm run build

# Stage 2: Serve with Nginx Alpine
FROM nginx:alpine AS production

# Copy built static files to Nginx default html dir
COPY --from=build /app/dist /usr/share/nginx/html

# Copy custom Nginx configuration
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
