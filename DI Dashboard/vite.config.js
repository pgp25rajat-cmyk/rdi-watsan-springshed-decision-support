// Served at /dashboard/ by the spring tool's server (scripts/spring_tool_server.py), and by server.py on its own
export default { base: "/dashboard/", build: { outDir: "dist" }, server: { proxy: { "/api": "http://127.0.0.1:8769" } } };
