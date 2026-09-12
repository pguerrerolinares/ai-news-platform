import { FeedPage } from './FeedPage'

export default function Latest() {
  return (
    <FeedPage
      title="Latest"
      description="Newest AI news"
      queryKeyPrefix="latest"
      sort="recent"
    />
  )
}
