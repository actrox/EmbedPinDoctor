import js from "@eslint/js";
import globals from "globals";

export default [
  {
    files: ["web/*.js"],
    languageOptions: {
      ecmaVersion: "latest",
      sourceType: "script",
      globals: globals.browser
    },
    rules: {
      ...js.configs.recommended.rules,
      "no-unused-vars": ["error", { "argsIgnorePattern": "^_" }]
    }
  }
];
