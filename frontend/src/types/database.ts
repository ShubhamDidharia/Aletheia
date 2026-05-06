export type Database = {
  public: {
    Tables: {
      users: {
        Row: {
          id: string
          email: string
          full_name: string | null
          avatar_url: string | null
          created_at: string
        }
      }
      missions: {
        Row: {
          id: string
          user_id: string
          title: string
          query: string
          status: 'idle' | 'running' | 'awaiting_input' | 'complete' | 'error'
          created_at: string
          updated_at: string
        }
      }
      sources: {
        Row: {
          id: string
          mission_id: string
          url: string
          title: string | null
          snippet: string | null
          source_type: 'web' | 'pdf' | 'sec_filing' | 'news'
          favicon_url: string | null
          scraped_at: string
        }
      }
      reports: {
        Row: {
          id: string
          mission_id: string
          output_type: 'table' | 'swot' | 'chart' | 'report'
          content: string | null
          structured_data: any
          embedding: number[] | null
          created_at: string
        }
      }
    }
  }
}
