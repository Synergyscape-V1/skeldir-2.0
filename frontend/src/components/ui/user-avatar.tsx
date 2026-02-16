import { Avatar, AvatarImage, AvatarFallback } from "@/components/ui/avatar";
import { Tooltip, TooltipTrigger, TooltipContent } from "@/components/ui/tooltip";

interface UserAvatarProps {
  userName: string;
  userEmail: string;
  userInitials: string;
  profileImageUrl?: string;
}

export default function UserAvatar({ userName, userEmail, userInitials, profileImageUrl }: UserAvatarProps) {
  return (
    <Tooltip delayDuration={500}>
      <TooltipTrigger asChild>
        <Avatar 
          className="h-8 w-8 lg:h-9 lg:w-9 cursor-default"
          data-testid="avatar-user-identity"
        >
          {profileImageUrl ? (
            <AvatarImage 
              src={profileImageUrl} 
              alt={userName}
              className="object-cover"
            />
          ) : null}
          <AvatarFallback
            className="bg-gray-700 text-white font-medium text-xs lg:text-sm"
          >
            {userInitials.toUpperCase()}
          </AvatarFallback>
        </Avatar>
      </TooltipTrigger>
      <TooltipContent
        side="bottom"
        sideOffset={8}
        className="bg-gray-900 text-white border-0 rounded shadow-lg"
      >
        {userName} | {userEmail}
      </TooltipContent>
    </Tooltip>
  );
}
