// Metro config tuned for the npm-workspaces monorepo: watch the repo root and
// resolve modules from both the app's and the root's node_modules (npm hoists
// most deps to the root).
// Uses Sentry's Expo metro wrapper so JS source maps upload correctly on EAS builds.
const { getSentryExpoConfig } = require('@sentry/react-native/metro');
const path = require('path');

const projectRoot = __dirname;
const workspaceRoot = path.resolve(projectRoot, '../..');

// getSentryExpoConfig wraps expo/metro-config's getDefaultConfig.
const config = getSentryExpoConfig(projectRoot);

config.watchFolders = [workspaceRoot];
config.resolver.nodeModulesPaths = [
  path.resolve(projectRoot, 'node_modules'),
  path.resolve(workspaceRoot, 'node_modules'),
];
config.resolver.disableHierarchicalLookup = true;

module.exports = config;
