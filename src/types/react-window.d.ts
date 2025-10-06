declare module 'react-window' {
  import * as React from 'react';

  export interface ListOnScrollProps {
    scrollDirection?: 'forward' | 'backward';
    scrollOffset: number;
    scrollUpdateWasRequested?: boolean;
  }

  export interface VariableSizeListProps {
    height: number;
    itemCount: number;
    itemSize: (index: number) => number;
    width: number | string;
    className?: string;
    style?: React.CSSProperties;
    onScroll?: (props: ListOnScrollProps) => void;
    outerElementType?: any;
    itemKey?: (index: number) => React.Key;
    overscanCount?: number;
    children: (params: { index: number; style: React.CSSProperties }) => React.ReactNode;
  }

  export class VariableSizeList extends React.Component<VariableSizeListProps> {
    scrollToItem(index: number, align?: 'auto' | 'smart' | 'center' | 'end' | 'start'): void;
    resetAfterIndex(index: number, shouldForceUpdate?: boolean): void;
  }

  export { VariableSizeList as List, VariableSizeList as FixedSizeList };
  export { VariableSizeList as ListOnScrollProps };
}


