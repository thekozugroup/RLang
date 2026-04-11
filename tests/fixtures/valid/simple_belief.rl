// Minimal valid trace with all 4 required phases

#[phase(Frame)]
{
    let rain: blf<0.95> = obs(rain) | p:0.95 | ep:direct | src:obs(sensor) | scope:loc | t:fresh;
}

#[phase(Explore)]
{
    let ev = [
        obs(dark_clouds) => sup(rain, +0.05),
    ];
    rain |> resolve(ev) -> Ok(confirmed);
}

#[phase(Verify)]
{
    req(rain, obs(rain)) |> verify(rain) -> Ok(());
}

#[phase(Decide)]
{
    match conf(rain) {
        c if c > 0.85 => assert(rain),
        _ => hedge(rain),
    }
}
