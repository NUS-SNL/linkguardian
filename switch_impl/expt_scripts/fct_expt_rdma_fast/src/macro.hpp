/*
	Copyright (C) 2023 Chahwan Song, National University of University
    skychahwan [at] gmail.com
    
    This program is free software: you can redistribute it and/or modify
    it under the terms of the GNU Affero General Public License as published by
    the Free Software Foundation, either version 3 of the License, or
    (at your option) any later version.
    This program is distributed in the hope that it will be useful,
    but WITHOUT ANY WARRANTY; without even the implied warranty of
    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
    GNU Affero General Public License for more details.
    You should have received a copy of the GNU Affero General Public License
    along with this program.  If not, see <https://www.gnu.org/licenses/>.
*/

#pragma once

namespace rdma_simple {

/* DEBUGGING MODE, 0: Error, 1: Info, 2: Debug */
#define RDMA_DEBUG_FLAG (0)

/* Default message size (bytes) */
#define DEFAULT_MESSAGE_SIZE (24387)

/*************************************************************
***           D E B U G G I N G   F U N C T I O N S        ***
**************************************************************/
/* Error Macro */
#if (RDMA_DEBUG_FLAG >= 0)
#define rdma_error(msg, args...) \
    fprintf(stderr, "%s : %d : ERROR : " msg, __FILE__, __LINE__, ##args);
#else
#define rdma_error(msg, args...)
#endif

/* Debug Macro */
#if (RDMA_DEBUG_FLAG >= 1)
#define rdma_info(msg, args...) \
    printf("INFO: " msg, ##args);
#else
#define rdma_info(msg, args...) 
#endif

/* Debug Macro */
#if (RDMA_DEBUG_FLAG >= 2)
#define debug(msg, args...) \
    printf("DEBUG: " msg, ##args);
#else
#define debug(msg, args...) 
#endif

} // namespace rdma_simple