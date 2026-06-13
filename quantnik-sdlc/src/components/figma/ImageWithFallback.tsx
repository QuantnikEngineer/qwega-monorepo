import React, { useState } from 'react'

const ERROR_IMG_SRC =
  'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iODgiIGhlaWdodD0iODgiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyIgc3Ryb2tlPSIjODg4IiBzdHJva2UtbGluZWpvaW49InJvdW5kIiBvcGFjaXR5PSIuNSIgZmlsbD0ibm9uZSIgc3Ryb2tlLXdpZHRoPSIyIj48cmVjdCB4PSIxNiIgeT0iMTYiIHdpZHRoPSI1NiIgaGVpZ2h0PSI1NiIgcng9IjQiLz48cGF0aCBkPSJtMjQgNDggMTYtMTYgMjQgMjQiLz48Y2lyY2xlIGN4PSI0NCIgY3k9IjMyIiByPSI0Ii8+PC9zdmc+'

export function ImageWithFallback(props: React.ImgHTMLAttributes<HTMLImageElement>) {
  const [didError, setDidError] = useState(false)
  const [isLoaded, setIsLoaded] = useState(false)

  const { src, alt, style, className, onLoad, onError, ...rest } = props

  const handleLoad = (e: React.SyntheticEvent<HTMLImageElement>) => {
    setIsLoaded(true)
    onLoad?.(e)
  }

  const handleError = (e: React.SyntheticEvent<HTMLImageElement>) => {
    setDidError(true)
    onError?.(e)
  }

  if (didError) {
    return (
      <div
        className={`inline-block bg-muted/20 text-center align-middle border border-border/20 rounded ${className ?? ''}`}
        style={style}
      >
        <div className="flex items-center justify-center w-full h-full p-4">
          <img src={ERROR_IMG_SRC} alt="Image failed to load" className="opacity-40 w-16 h-16" />
        </div>
      </div>
    )
  }

  return (
    <img
      src={src}
      alt={alt}
      className={className}
      style={style}
      onLoad={handleLoad}
      onError={handleError}
      {...rest}
    />
  )
}
