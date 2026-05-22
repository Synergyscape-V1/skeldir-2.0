"use client";

import { categories, CategoryFilter as CategoryFilterType } from "@/data/articlesData";

interface CategoryFilterProps {
    activeCategory: CategoryFilterType;
    onCategoryChange: (category: CategoryFilterType) => void;
}

export function CategoryFilter({ activeCategory, onCategoryChange }: CategoryFilterProps) {
    return (
        <nav
            aria-label="Article category filters"
            className="w-full pt-2 md:pt-3 pb-4 md:pb-6"
        >
            <div className="container mx-auto px-4 md:px-6">
                <div
                    className="flex items-center gap-2 md:gap-4 overflow-x-auto pb-2 scrollbar-hide"
                    style={{
                        scrollSnapType: 'x mandatory',
                        WebkitOverflowScrolling: 'touch',
                    }}
                >
                    {categories.map((category) => {
                        const isActive = activeCategory === category;
                        return (
                            <button
                                key={category}
                                onClick={() => onCategoryChange(category)}
                                aria-current={isActive ? 'true' : undefined}
                                className="flex-shrink-0 transition-all duration-200"
                                style={{
                                    scrollSnapAlign: 'center',
                                    fontWeight: isActive ? 600 : 400,
                                    fontSize: '15px',
                                    color: isActive ? '#2563EB' : '#4B5563',
                                    backgroundColor: 'transparent',
                                    border: 'none',
                                    borderBottom: isActive ? '2px solid #2563EB' : '2px solid transparent',
                                    borderRadius: '0',
                                    padding: '0',
                                    margin: '0',
                                    outline: 'none',
                                    cursor: 'pointer',
                                }}
                                onMouseEnter={(e) => {
                                    if (!isActive) {
                                        e.currentTarget.style.borderBottom = '2px solid #D1D5DB';
                                    }
                                }}
                                onMouseLeave={(e) => {
                                    if (!isActive) {
                                        e.currentTarget.style.borderBottom = '2px solid transparent';
                                    }
                                }}
                                onMouseDown={(e) => {
                                    e.currentTarget.style.backgroundColor = 'transparent';
                                }}
                                onMouseUp={(e) => {
                                    e.currentTarget.style.backgroundColor = 'transparent';
                                }}
                            >
                                {category}
                            </button>
                        );
                    })}
                </div>
                {/* Subtle separator line */}
                <div
                    className="w-full mt-2"
                    style={{
                        height: '1px',
                        backgroundColor: '#E5E7EB',
                    }}
                />
            </div>
        </nav>
    );
}
