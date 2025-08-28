from smartwealth_data.services.fetchers.yahoo_earnings_fetcher import YahooEarningsFetcher

def test_fetcher_ctor():
    f = YahooEarningsFetcher(months_back=1)
    assert f.cutoff is not None
