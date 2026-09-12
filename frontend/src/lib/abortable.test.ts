import { describe, it, expect } from 'vitest'
import { createAbortSwitch } from './abortable'

describe('createAbortSwitch', () => {
  it('aborts the previous in-flight signal when a new one starts (search-abort race)', () => {
    const switcher = createAbortSwitch()

    const firstSearch = switcher.next()
    expect(firstSearch.aborted).toBe(false)

    // A new search starts before the first one resolved.
    const secondSearch = switcher.next()

    expect(firstSearch.aborted).toBe(true)
    expect(secondSearch.aborted).toBe(false)
  })

  it('abort() cancels the current in-flight signal (e.g. on unmount)', () => {
    const switcher = createAbortSwitch()
    const signal = switcher.next()

    switcher.abort()

    expect(signal.aborted).toBe(true)
  })
})
