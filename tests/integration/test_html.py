def test_index_renders(raw_client):
    r = raw_client.get("/")
    assert r.status_code == 200
    assert "Job Application Assistant" in r.text
    assert 'class="file-input"' in r.text


def test_prune_button_hidden_when_no_flagged_claims(
    client, repo, settings, fixed_clock, seq_ids, app
):
    from jaa.samples import seed

    seed(repo, settings, fixed_clock, seq_ids, app.state.lexicon)
    job = repo.list_jobs()[0]
    run = client.post(f"/api/jobs/{job.id}/runs", json={}).json()
    client.post(f"/api/runs/{run['id']}/prune")
    pruned_id = client.post(f"/api/runs/{run['id']}/prune").json()["id"]
    page = client.raw.get(f"/runs/{pruned_id}")
    assert page.status_code == 200
    assert 'data-testid="prune-button"' not in page.text
