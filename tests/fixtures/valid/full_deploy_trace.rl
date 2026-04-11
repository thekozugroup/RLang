// Full deployment decision trace from the RLang spec

#[phase(Frame)]
impl Deductive {
    let tests: blf<0.99> = obs(tests_pass) | p:0.99 | ep:direct | src:ci_pipeline | scope:loc | t:fresh;
    let risk: blf<0.85> = obs(no_rollback) | p:0.85 | ep:direct | src:obs(infra) | scope:loc | t:fresh;
    let traffic: blf<0.90> = obs(low_traffic) | p:0.90 | ep:direct | src:obs(metrics) | scope:loc | t:fresh;
}

#[phase(Explore)]
{
    let ev = [
        tests => sup(deploy, +0.15),
        risk => wkn(deploy, -0.25),
        traffic => sup(deploy, +0.10),
    ];
    deploy |> resolve(ev) -> Ok(ready);
}

#[phase(Verify)]
{
    req(tests, obs(tests_pass)) |> verify(deploy) -> Ok(());
}

#[phase(Decide)]
{
    match conf(deploy) {
        c if c > 0.80 => assert(deploy),
        c if c > 0.50 => hedge(deploy),
        _ => suspend(deploy),
    }
}
