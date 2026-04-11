// Invalid: skips the Verify phase (Frame -> Explore -> Decide)

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

#[phase(Decide)]
{
    assert(rain) | p:0.92;
}
