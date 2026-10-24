-- Thin executor assembly. Reviewed pins and Ember arrive from the release package.
-- No network or gameplay action runs until start is explicitly called.
local ExecutorEntry = {}

function ExecutorEntry.start(release, services, activateRuntime)
    if type(release) ~= "table" or type(services) ~= "table"
        or type(services.ReleaseAdapters) ~= "table"
        or type(services.ReleaseAdapters.new) ~= "function"
        or type(services.Bootstrap) ~= "table"
        or type(services.Bootstrap.start) ~= "function"
        or type(services.executorEnv) ~= "table"
        or type(services.executorEnv.crypt) ~= "table"
        or type(services.executorEnv.crypt.hash) ~= "function"
        or type(services.httpGet) ~= "function"
        or type(services.compile) ~= "function" then
        return nil, "Missing executor entry services"
    end
    local env = services.executorEnv
    local releaseIO, reason = services.ReleaseAdapters.new(
        release.commit, {
            httpGet = services.httpGet,
            isfolder = env.isfolder,
            makefolder = env.makefolder,
            isfile = env.isfile,
            readfile = env.readfile,
            writefile = env.writefile,
            compile = services.compile,
        })
    if not releaseIO then return nil, reason end
    return services.Bootstrap.start(release, {
        Loader = services.Loader,
        Manifest = services.Manifest,
        fetch = releaseIO.fetch,
        cache = releaseIO.cache,
        compile = releaseIO.compile,
        clientGame = services.clientGame,
        clientRequire = services.clientRequire,
        clientHash = env.crypt.hash,
        executorEnv = env,
        scheduler = services.scheduler,
        Ember = services.Ember,
    }, activateRuntime)
end

return ExecutorEntry
