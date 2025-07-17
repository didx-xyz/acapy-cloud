load("./tilt/acapy-cloud/Tiltfile", "setup_cloudapi")
load("./tilt/metrics/Tiltfile", "setup_metrics_server")
load("./tilt/utils/Tiltfile", "run_command")
load("ext://color", "color")
load("ext://helm_resource", "helm_repo")
load("ext://uibutton", "cmd_button", "location", "choice_input")

config.define_bool("no-build", False, "Skip building Docker images")
config.define_bool("destroy", False, "Destroy Kind cluster")
config.define_bool(
    "destroy-all",
    False,
    "Destroy Kind cluster and delete docker registry & cache",
)
config.define_bool(
    "expose",
    False,
    "Detect Host IP and set Ingress Domain Name to expose services outside of 'localhost' context",
)
config.define_bool("no-cheqd")
cfg = config.parse()


update_settings(
    k8s_upsert_timeout_secs=600,
    max_parallel_updates=5,
)

# Restrict to `kind-acapy-cloud` kube context
kind_cluster_name = "kind-acapy-cloud"
allow_k8s_contexts([kind_cluster_name])

if config.tilt_subcommand in ("up", "ci"):
    print(color.green("Ensuring submodules are initialized"))
    run_command(
        "git submodule status | awk '/^-/ {print $2}' | xargs -r git submodule update --init",
        dir=os.path.dirname(__file__),
    )
    print(color.green("Setting up Istio"))
    local_resource(
        name="istio",
        cmd="mise run kind:install:istio",
        allow_parallel=True,
        labels=["99-networking"],
    )

    print(color.green("Setting up Ingress Nginx"))
    local_resource(
        name="ingress-nginx",
        cmd="mise run kind:install:nginx",
        allow_parallel=True,
        labels=["99-networking"],
        deps=["./tilt/ingress_nginx/values.yaml"],
    )

# Setup Metrics Server
setup_metrics_server()

cmd_button(
    name="expose",
    icon_name="public",  # https://fonts.google.com/icons
    text="Expose Ingresses via Tailscale or Local Network",
    location=location.NAV,
    argv=[
        "tilt",
        "patch",
        "tiltfile",
        "(Tiltfile)",
        "--patch",
        '{"spec": {"args": ["--expose=True"]}}',
    ],
)

cmd_button(
    name="unexpose",
    icon_name="public_off",
    text="Switch Ingresses back to 'localhost'",
    location=location.NAV,
    argv=[
        "tilt",
        "patch",
        "tiltfile",
        "(Tiltfile)",
        "--patch",
        '{"spec": {"args": ["--expose=False"]}}',
    ],
)

# Setup acapy-cloud
build_enabled = not cfg.get("no-build")
expose = cfg.get("expose")
cheqd_self_hosted = not cfg.get("no-cheqd")
setup_cloudapi(build_enabled, expose, cheqd_self_hosted)

if config.tilt_subcommand not in ("down"):
    # _FORCE_ Kube Context to `kind-acapy-cloud`
    local(
        "kubectl config use-context " + kind_cluster_name, dir=os.path.dirname(__file__)
    )

if config.tilt_subcommand in ("down"):
    destroy = config.parse().get("destroy")
    destroy_all = config.parse().get("destroy-all")

    if destroy_all:
        print(color.red("Destroying Kind cluster and deleting docker registry & cache"))
        local("mise run kind:destroy:all", dir=os.path.dirname(__file__))

    if destroy:
        print(color.red("Destroying Kind cluster"))
        local("mise run kind:destroy", dir=os.path.dirname(__file__))
