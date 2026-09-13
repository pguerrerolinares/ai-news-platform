import { FeedPage } from './FeedPage'

export default function Top() {
  return (
    <FeedPage
      title="Top"
      description="Most relevant AI news"
      queryKeyPrefix="feed"
      sort="relevance"
    />
  )
}
