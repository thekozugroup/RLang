#[phase(Frame)]
impl Deductive {
    let tests: blf<0.99> = obs(tests_pass) | p:0.99 | ep:direct | src:ci_pipeline | scope:loc | t:fresh;
    let risk: blf<0.85> = obs(no_rollback) | p:0.85 | ep:direct | src:obs(infra) | scope:loc | t:fresh;
    let traffic: blf<0.70> = obs(high_traffic) | p:0.70 | ep:direct | src:obs(monitoring) | scope:loc | t:fresh;
}

#[phase(Explore)]
{
    let ev = [
        tests => sup(deploy, +0.15),
        risk  => wkn(deploy, -0.25),
    ];
    let deploy_blf = enbl(fix, resolve(bug)) |> resolve(ev) -> Ok(blf_resolved);
}

#[phase(Verify)]
{
    req(deploy, obs(tests_pass)) |> verify(tests) -> Ok(());
}

#[phase(Decide)]
{
    match conf(deploy_blf) {
        c if c > 0.80 => assert(deploy),
        c if c > 0.55 => hedge(deploy),
        _ => reject(deploy),
    }
}
